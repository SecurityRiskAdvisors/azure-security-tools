#!/usr/bin/env python3  
import os  
import sys  
import json  
import re  
import tempfile  
import traceback  
from pathlib import Path  
from typing import Dict, List, Tuple, Set  
from urllib.parse import urlparse, urlunparse  
  
import pandas as pd  
from tqdm import tqdm  
  
from azure.identity import DefaultAzureCredential  
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder  
from azure.kusto.data.data_format import DataFormat  
from azure.kusto.ingest import (  
    QueuedIngestClient,  
    IngestionProperties,  
    IngestionMappingKind,  
)  
  
# Constants  
DEFAULT_SCOPE = "https://kusto.kusto.windows.net/.default"  
CUSTOM_DELIMITER = "❖"  
MAPPING_NAME = "csv_map"  
  
  
def prompt_user_inputs() -> Tuple[str, str, Path]:  
    # Require cluster URL; no default  
    cluster_url = ""  
    while not cluster_url:  
        cluster_url = input(  
            "Enter Azure Data Explorer (Kusto) cluster URL "  
            "(e.g., https://yourclustername.eastus.kusto.windows.net): "  
        ).strip()  
        if not cluster_url:  
            print("Cluster URL is required. Please enter a valid cluster URL.")  
  
    database = input("Enter ADX database name: ").strip()  
  
    incidents_dir = Path.cwd() / "incidents"  
    if not incidents_dir.exists() or not incidents_dir.is_dir():  
        print(  
            f"ERROR: '{incidents_dir}' does not exist or is not a directory. "  
            f"Please run from a directory that contains an 'incidents' folder."  
        )  
        sys.exit(1)  
  
    subfolders = sorted([p for p in incidents_dir.iterdir() if p.is_dir()])  
    if not subfolders:  
        print(f"ERROR: No incident folders found under '{incidents_dir}'.")  
        sys.exit(1)  
  
    print("\nAvailable incident folders:")  
    for idx, p in enumerate(subfolders, start=1):  
        print(f"  {idx}) {p.name}")  
  
    choice = None  
    while choice is None:  
        raw = input("Select an incident folder by number [default: 1]: ").strip()  
        if raw == "":  
            choice = 1  
            break  
        if raw.isdigit():  
            num = int(raw)  
            if 1 <= num <= len(subfolders):  
                choice = num  
                break  
        print(f"Invalid selection. Enter a number between 1 and {len(subfolders)}.")  
  
    folder = subfolders[choice - 1]  
  
    if not cluster_url.startswith("https://"):  
        cluster_url = "https://" + cluster_url  
  
    return cluster_url, database, folder  
  
  
def ensure_ingest_url(cluster_url: str) -> str:  
    """  
    Return the ingest endpoint for the given cluster URL by prefixing 'ingest-' to the host.  
    """  
    parsed = urlparse(cluster_url)  
    netloc = parsed.netloc  
    if not netloc.startswith("ingest-"):  
        netloc = f"ingest-{netloc}"  
    ingest_url = urlunparse(  
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)  
    )  
    return ingest_url  
  
  
def build_token_provider(credential: DefaultAzureCredential):  
    def _token_provider():  
        token = credential.get_token(DEFAULT_SCOPE)  
        return token.token  
  
    return _token_provider  
  
  
def create_kcsb_with_credential(  
    url: str, credential: DefaultAzureCredential  
) -> KustoConnectionStringBuilder:  
    """  
    Create a KustoConnectionStringBuilder using the best available auth method  
    in the installed azure-kusto-data version.  
    """  
    kcsb_cls = KustoConnectionStringBuilder  
  
    # Preferred in newer versions: directly use Azure credential  
    if hasattr(kcsb_cls, "with_azure_token_credential"):  
        return kcsb_cls.with_azure_token_credential(url, credential)  
  
    token_provider = build_token_provider(credential)  
  
    # Older/newer variants:  
    if hasattr(kcsb_cls, "with_aad_token_provider"):  
        return kcsb_cls.with_aad_token_provider(url, token_provider)  
  
    if hasattr(kcsb_cls, "with_async_token_provider"):  
  
        async def async_provider():  
            return token_provider()  
  
        return kcsb_cls.with_async_token_provider(url, async_provider)  
  
    if hasattr(kcsb_cls, "with_aad_token"):  
        # Fallback: fetch one token up front (non-refreshing)  
        return kcsb_cls.with_aad_token(url, token_provider())  
  
    raise RuntimeError(  
        "Unable to configure KustoConnectionStringBuilder with the installed azure-kusto-data package. "  
        "Please upgrade 'azure-kusto-data' to a version that supports one of: "  
        "with_azure_token_credential, with_aad_token_provider, with_async_token_provider, or with_aad_token."  
    )  
  
  
def get_kusto_clients(  
    cluster_url: str, credential: DefaultAzureCredential  
) -> Tuple[KustoClient, QueuedIngestClient]:  
    data_kcsb = create_kcsb_with_credential(cluster_url, credential)  
    data_client = KustoClient(data_kcsb)  
  
    ingest_url = ensure_ingest_url(cluster_url)  
    ingest_kcsb = create_kcsb_with_credential(ingest_url, credential)  
    ingest_client = QueuedIngestClient(ingest_kcsb)  
  
    return data_client, ingest_client  
  
  
def base_name_from_stem(stem: str) -> str:  
    """  
    Return the base name by removing a trailing _<number> segment, if present.  
    Examples:  
      'AzureMetrics' -> 'AzureMetrics'  
      'AzureMetrics_0' -> 'AzureMetrics'  
      'Azure_Metrics_2024_1' -> 'Azure_Metrics_2024'  
    """  
    return re.sub(r"_\d+$", "", stem)  
  
  
def suffix_index_from_stem(stem: str) -> int:  
    """  
    Return the numeric suffix index if present, else -1 for unsuffixed.  
    AzureMetrics -> -1, AzureMetrics_0 -> 0, AzureMetrics_2 -> 2  
    """  
    m = re.search(r"_(\d+)$", stem)  
    return int(m.group(1)) if m else -1  
  
  
def find_csv_meta_pairs(root_folder: Path) -> List[Tuple[Path, Path]]:  
    """  
    Traverse the incident folder (including one level deeper) to find CSVs and their meta.  
    Match CSVs to a single meta by base name (stem without trailing _<number>).  
    For multi-file datasources (folder with *_0.csv, *_1.csv, ...),  
    prefer the *_0.meta (or the lowest index) for the base.  
    Returns list of (csv_path, meta_path), sorted by base and segment index.  
    """  
    # Map base -> best meta path (choose lowest suffix index, with unsuffixed preferred)  
    meta_by_base: Dict[str, Path] = {}  
    meta_weight: Dict[str, int] = {}  
  
    for meta in root_folder.rglob("*.meta"):  
        base = base_name_from_stem(meta.stem)  
        idx = suffix_index_from_stem(meta.stem)  
        weight = idx if idx >= 0 else -1  # unsuffixed gets weight -1 (preferred)  
        if base not in meta_by_base or weight < meta_weight[base]:  
            meta_by_base[base] = meta  
            meta_weight[base] = weight  
  
    # Group CSVs by base and sort each group by suffix index (unsuffixed first, then 0,1,2,...)  
    csvs_by_base: Dict[str, List[Path]] = {}  
    for csv in root_folder.rglob("*.csv"):  
        base = base_name_from_stem(csv.stem)  
        csvs_by_base.setdefault(base, []).append(csv)  
  
    for base, lst in csvs_by_base.items():  
        lst.sort(key=lambda p: suffix_index_from_stem(p.stem))  
  
    # Build pairs  
    pairs: List[Tuple[Path, Path]] = []  
    for base, lst in sorted(csvs_by_base.items(), key=lambda kv: kv[0].lower()):  
        meta = meta_by_base.get(base)  
        if not meta or not meta.exists():  
            for csv in lst:  
                print(  
                    f"WARNING: No matching meta file found for {csv} (expected {base}_0.meta or {base}.meta)"  
                )  
            continue  
        for csv in lst:  
            pairs.append((csv, meta))  
  
    return pairs  
  
  
def load_meta(meta_path: Path) -> Dict[str, str]:  
    """  
    Meta file is JSON: {"Column":"type", ...}  
    """  
    try:  
        raw = meta_path.read_text(encoding="utf-8").strip()  
        if raw.endswith("%"):  
            raw = raw[:-1]  
        meta = json.loads(raw)  
        return meta  
    except Exception as e:  
        raise RuntimeError(f"Failed to parse meta file {meta_path}: {e}")  
  
  
def read_header_and_delimiter(csv_path: Path) -> Tuple[List[str], str]:  
    """  
    Read the first line as header; detect delimiter (❖ or comma).  
    """  
    with csv_path.open("r", encoding="utf-8-sig", errors="replace") as f:  
        header_line = f.readline().strip()  
    delimiter = CUSTOM_DELIMITER if CUSTOM_DELIMITER in header_line else ","  
    header = [h.strip() for h in header_line.split(delimiter) if h.strip() != ""]  
    return header, delimiter  
  
  
def safe_kusto_identifier(name: str) -> str:  
    return f"[{name}]"  
  
  
def build_create_table_command(  
    table_name: str, schema: Dict[str, str], header: List[str]  
) -> str:  
    """  
    Order columns based on header; default missing types to string; append meta-only columns at end.  
    """  
    ordered_cols = []  
    seen = set()  
    for col in header:  
        if col in schema:  
            ordered_cols.append((col, schema[col]))  
        else:  
            ordered_cols.append((col, "string"))  
            print(  
                f"WARNING: Column '{col}' present in CSV header but missing in meta; defaulting to 'string'."  
            )  
        seen.add(col)  
  
    remaining = [(c, t) for c, t in schema.items() if c not in seen]  
    if remaining:  
        print(  
            f"WARNING: {len(remaining)} meta columns not found in header. They will be appended at the end."  
        )  
        ordered_cols.extend(remaining)  
  
    col_defs = ", ".join(f"{safe_kusto_identifier(c)}:{t}" for c, t in ordered_cols)  
    cmd = f".create-merge table {safe_kusto_identifier(table_name)} ({col_defs})"  
    return cmd  
  
  
def build_csv_mapping_json(header: List[str], schema: Dict[str, str]) -> List[Dict]:  
    """  
    Build a CSV ingestion mapping (JSON form) aligned to header order for the Kusto management command.  
    """  
    return [  
        {"column": col, "datatype": schema.get(col, "string"), "ordinal": i}  
        for i, col in enumerate(header)  
    ]  
  
  
def ensure_table_and_mapping(  
    data_client: KustoClient,  
    database: str,  
    table_name: str,  
    meta: Dict[str, str],  
    header: List[str],  
) -> None:  
    # Create or merge table schema  
    create_cmd = build_create_table_command(table_name, meta, header)  
    data_client.execute_mgmt(database, create_cmd)  
  
    # Create or alter CSV ingestion mapping  
    mapping_json = json.dumps(build_csv_mapping_json(header, meta))  
    mapping_cmd = (  
        f".create-or-alter table {safe_kusto_identifier(table_name)} ingestion csv "  
        f"mapping '{MAPPING_NAME}' '{mapping_json}'"  
    )  
    data_client.execute_mgmt(database, mapping_cmd)  
  
  
def convert_custom_csv_to_standard(csv_path: Path, header: List[str], delimiter: str) -> Path:  
    """  
    Convert the source CSV to a temporary comma-separated CSV using pandas in chunks.  
    Keeps all values as strings; ADX will cast per mapping datatypes.  
    """  
    tmp_fd, tmp_path_str = tempfile.mkstemp(prefix="adx_", suffix=".csv")  
    os.close(tmp_fd)  
    tmp_path = Path(tmp_path_str)  
  
    # Write header to the temp CSV (ignored by ingestion via ignoreFirstRecord)  
    tmp_path.write_text(",".join(header) + "\n", encoding="utf-8")  
  
    # Chunked read and append rows  
    progress = tqdm(desc=f"Converting {csv_path.name}", unit="rows")  
    reader = pd.read_csv(  
        csv_path,  
        sep=delimiter,  
        engine="python",  # use python engine for flexibility with custom delimiter  
        header=0,  
        dtype=str,  
        chunksize=100_000,  
        on_bad_lines="skip",  
    )  
    with tmp_path.open("a", encoding="utf-8", newline="") as fout:  
        for chunk in reader:  
            # Ensure all header columns exist  
            for col in header:  
                if col not in chunk.columns:  
                    chunk[col] = ""  
            # Reorder columns to match mapping header order  
            chunk = chunk[header]  
            chunk.to_csv(fout, index=False, header=False)  
            progress.update(len(chunk))  
    progress.close()  
  
    return tmp_path  
  
  
def ingest_file(  
    ingest_client: QueuedIngestClient,  
    database: str,  
    table_name: str,  
    file_path: Path,  
) -> None:  
    """  
    Queue ingestion of the converted CSV file using the named mapping created via management commands.  
    """  
    ingestion_props = IngestionProperties(  
        database=database,  
        table=table_name,  
        data_format=DataFormat.CSV,  
        ingestion_mapping_reference=MAPPING_NAME,  
        ingestion_mapping_kind=IngestionMappingKind.CSV,  
        additional_properties={"ignoreFirstRecord": True},  
    )  
    ingest_client.ingest_from_file(str(file_path), ingestion_properties=ingestion_props)  
  
  
def process_pair(  
    data_client: KustoClient,  
    ingest_client: QueuedIngestClient,  
    database: str,  
    csv_path: Path,  
    meta_path: Path,  
    tables_initialized: Set[str],  
    table_headers: Dict[str, List[str]],  
    table_delimiters: Dict[str, str],  
) -> None:  
    base = base_name_from_stem(csv_path.stem)  
    table_name = base  
    print(f"\nProcessing table '{table_name}' from '{csv_path}'")  
  
    # Initialize table and mapping only once per table (based on first CSV encountered)  
    if table_name not in tables_initialized:  
        meta = load_meta(meta_path)  
        header, delimiter = read_header_and_delimiter(csv_path)  
        if not header:  
            raise RuntimeError(f"No header line detected in {csv_path}")  
  
        ensure_table_and_mapping(data_client, database, table_name, meta, header)  
        table_headers[table_name] = header  
        table_delimiters[table_name] = delimiter  
        tables_initialized.add(table_name)  
    else:  
        # Reuse the header and delimiter captured for the table  
        header = table_headers[table_name]  
        delimiter = table_delimiters[table_name]  
  
    tmp_csv = convert_custom_csv_to_standard(csv_path, header, delimiter)  
    try:  
        ingest_file(ingest_client, database, table_name, tmp_csv)  
        print(  
            f"Queued ingestion for table '{table_name}' from '{csv_path.name}'. Temporary file: {tmp_csv}"  
        )  
    finally:  
        # Keep temp file for troubleshooting; uncomment to remove:  
        # os.remove(tmp_csv)  
        pass  
  
  
def main():  
    try:  
        cluster_url, database, root_folder = prompt_user_inputs()  
        print(  
            f"\nConnecting to ADX cluster: {cluster_url}\nDatabase: {database}\nRoot folder: {root_folder}"  
        )  
  
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)  
        data_client, ingest_client = get_kusto_clients(cluster_url, credential)  
  
        pairs = find_csv_meta_pairs(root_folder)  
        if not pairs:  
            print("No CSV/.meta pairs found under the selected incident folder.")  
            return  
  
        print(f"Found {len(pairs)} CSV/.meta pairs. Starting import...")  
  
        overall_progress = tqdm(total=len(pairs), desc="Overall progress", unit="file")  
        failures: List[Tuple[Path, str]] = []  
        tables_initialized: Set[str] = set()  
        table_headers: Dict[str, List[str]] = {}  
        table_delimiters: Dict[str, str] = {}  
  
        for csv_path, meta_path in pairs:  
            try:  
                process_pair(  
                    data_client,  
                    ingest_client,  
                    database,  
                    csv_path,  
                    meta_path,  
                    tables_initialized,  
                    table_headers,  
                    table_delimiters,  
                )  
            except Exception as e:  
                print(f"ERROR processing {csv_path.name}: {e}")  
                traceback.print_exc()  
                failures.append((csv_path, str(e)))  
            finally:  
                overall_progress.update(1)  
        overall_progress.close()  
  
        print("\nImport queued.")  
        if failures:  
            print(f"\nThere were {len(failures)} failures:")  
            for path, err in failures:  
                print(f"- {path}: {err}")  
            print("\nCheck ingestion failures in Kusto with:")  
            print(f"  .show ingestion failures | where Database == '{database}'")  
        else:  
            print("All files queued for ingestion successfully.")  
            print("Note: Ingestion is asynchronous; data may take time to appear.")  
  
    except KeyboardInterrupt:  
        print("\nInterrupted by user.")  
    except Exception as e:  
        print(f"\nFatal error: {e}")  
        traceback.print_exc()  
  
  
if __name__ == "__main__":  
    main()  