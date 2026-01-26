import os  
import json  
import time  
import requests  
import random  
from datetime import datetime  
import re  
  
QUESTIONS_DIR = "questions"  
RESULTS_DIR = "results"  
DEFAULT_AI_ENDPOINT_URL = "http://localhost:8000"  
  
  
def welcome_message():  
    print("=" * 70)  
    print("Welcome to ExCyTIn-Bench Testing Toolkit for AI Endpoints")  
    print("=" * 70)  
  
  
def main_menu():  
    print("\nMain Menu:")  
    print("1) Run Testing")  
    print("2) Score Results")  
    print("3) Help")  
    print("0) Exit")  
    choice = input("Select an option: ").strip()  
    return choice  
  
  
def show_help():  
    print("\n=== Help: AI Endpoint Integration ===\n")  
    print("This tool runs question/answer tests against a configurable AI Endpoint and")  
    print("optionally scores the AI answers against an answer key.\n")  
  
    print("Configuration:")  
    print("  For both Testing and Scoring you will be prompted for:")  
    print("    - AI Endpoint webhook URL")  
    print("    - Optional custom HTTP header name and value (for auth, etc.)\n")  
  
    print("Testing mode - request/response format:")  
    print("  1) Initial request (submit a question)")  
    print("     POST <AI Endpoint URL>")  
    print("     JSON body:")  
    print('     {')  
    print('       "mode": "testing",')  
    print('       "context": "<full context text>",')  
    print('       "question": "<question text>",')  
    print('       "incidentNumber": 1')  
    print("     }")  
    print()  
    print("  2) Initial response (job accepted)")  
    print("     HTTP 202 Accepted")  
    print("     {")  
    print('       "token": "<job token>"')  
    print("     }")  
    print()  
    print("  3) Polling request (performed by this tool every 10 seconds)")  
    print("     POST <AI Endpoint URL>")  
    print("     {")  
    print('       "mode": "polling",')  
    print('       "token": "<job token>"')  
    print("     }")  
    print()  
    print("  4) Polling responses")  
    print("     - While processing: HTTP 202 (body optional).")  
    print("     - When complete: HTTP 200 with:")  
    print("       {")  
    print('         "aiAnswer": "<model answer>",')  
    print('         "aiRationale": "<model reasoning / trace>"')  
    print("       }")  
    print()  
    print("  The tool stores one JSON object per question in a results file, e.g.:")  
    print("  {")  
    print('    "test_number": 1,')  
    print('    "incidentNumber": 1,')  
    print('    "retest": 0,')  
    print('    "context": "...",')  
    print('    "question": "...",')  
    print('    "answer": "<answer key>",')  
    print('    "aiAnswer": "<model answer>",')  
    print('    "aiRationale": "<model reasoning>",')  
    print('    "aiFullResponse": { ... }')  
    print("  }")  
    print()  
  
    print("Scoring mode - request/response format:")  
    print("  For each question already tested, the tool sends:")  
    print("  POST <AI Endpoint URL>")  
    print("  {")  
    print('    "mode": "scoring",')  
    print('    "context": "<original context>",')  
    print('    "question": "<original question>",')  
    print('    "answerKey": "<ground-truth answer>",')  
    print('    "aiAnswer": "<model answer from testing>",')  
    print('    "aiRationale": "<model rationale from testing>"')  
    print("  }")  
    print("  Expected scoring response (synchronous, HTTP 200):")  
    print("  {")  
    print('    "result": "correct" | "incorrect",')  
    print('    "score": 0.0-1.0,')  
    print('    "scoringRationale": "<why the answer was scored that way>"')  
    print("  }")  
    print()  
    print("  The tool writes these entries to a scoring JSON file, e.g.:")  
    print("  {")  
    print('    "test_number": 1,')  
    print('    "incidentNumber": 1,')  
    print('    "context": "...",')  
    print('    "question": "...",')  
    print('    "answer": "<answer key>",')  
    print('    "aiAnswer": "<model answer>",')  
    print('    "aiRationale": "<model rationale>",')  
    print('    "result": "correct",')  
    print('    "score": 1.0,')  
    print('    "scoringRationale": "<explanation from AI Endpoint>",')  
    print('    "aiScoringFullResponse": { ... }')  
    print("  }")  
    print()  
    print("Retesting / restarting:")  
    print("  - Restart existing test: continue a run, retest incorrect items, or retest abends.")  
    print("  - Retest individual items: pick specific test_numbers to rerun.")  
    print("All network calls for these operations use the same AI Endpoint webhook")  
    print("interface described above (modes: 'testing', 'polling', and 'scoring').\n")  
  
  
def list_incidents():  
    path = QUESTIONS_DIR  
    try:  
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]  
    except FileNotFoundError:  
        print(f"Questions directory not found: {path}")  
        return []  
  
  
def confirm_start():  
    confirm = input("Begin? (y/n): ").strip().lower()  
    return confirm == "y"  
  
  
def create_test_round_name(incident_name):  
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  
    return f"test_{incident_name}_{timestamp}"  
  
  
def parse_test_round_name(test_round_name):  
    """  
    Parse a test folder name created by create_test_round_name.  
  
    Expected format:  
        test_{incident_name}_{YYYYMMDD}_{HHMMSS}  
  
    Example:  
        test_incident_5_20251210_203745  
        -> incident_name = "incident_5"  
           timestamp     = "20251210_203745"  
  
    Returns (incident_name, timestamp) or (None, None)  
    if the name does not match the expected pattern.  
    """  
    if not test_round_name.startswith("test_"):  
        return None, None  
  
    rest = test_round_name[len("test_") :]  
    parts = rest.split("_")  
  
    if len(parts) < 3:  
        return None, None  
  
    date_part = parts[-2]  
    time_part = parts[-1]  
    timestamp = f"{date_part}_{time_part}"  
  
    incident_parts = parts[:-2]  
    if not incident_parts:  
        return None, None  
    incident_name = "_".join(incident_parts)  
  
    return incident_name, timestamp  
  
  
def load_questions(incident_name):  
    folder_path = os.path.join(QUESTIONS_DIR, incident_name)  
    if not os.path.isdir(folder_path):  
        print(f"Incidents folder not found: {folder_path}")  
        return []  
    files = [f for f in os.listdir(folder_path) if f.endswith(".json")]  
    if not files:  
        print(f"No JSON question file found for {incident_name}")  
        return []  
    json_path = os.path.join(folder_path, files[0])  
    with open(json_path, "r", encoding="utf-8") as f:  
        return json.load(f)  
  
  
def select_test_approach(total_questions):  
    """  
    Return a list of zero-based question indices to run, based on the  
    selected test approach.  
    """  
    print("\nSelect Test Approach:")  
    print("1) Run all tests")  
    print("2) Run first 5 questions (quick test)")  
    print("3) Run 10 random questions")  
    choice = input("Select an option: ").strip()  
  
    if total_questions <= 0:  
        return []  
  
    if choice == "2":  
        limit = min(5, total_questions)  
        return list(range(limit))  
    elif choice == "3":  
        count = min(10, total_questions)  
        indices = list(range(total_questions))  
        return random.sample(indices, count)  
    else:  
        return list(range(total_questions))  
  
  
def get_ai_endpoint_config(purpose):  
    """  
    Prompt for AI Endpoint webhook URL and optional custom header name/value.  
    Returns (url, headers_dict).  
    """  
    print(f"\nConfigure AI Endpoint for {purpose}:")  
    url = input(  
        f"Enter AI Endpoint webhook URL (default: {DEFAULT_AI_ENDPOINT_URL}): "  
    ).strip()  
    if not url:  
        url = DEFAULT_AI_ENDPOINT_URL  
  
    headers = {}  
    header_name = input(  
        "Optional custom header name for authentication (or leave blank): "  
    ).strip()  
    if header_name:  
        header_value = input(  
            f"Enter value for header '{header_name}': "  
        ).strip()  
        if header_value:  
            headers[header_name] = header_value  
  
    return url, headers  
  
  
def submit_question_to_ai_endpoint(  
    ai_endpoint_url, headers, context, question, incident_number  
):  
    """  
    Submit a question to the AI Endpoint in 'testing' mode and return the job token.  
    Expects HTTP 202 (or 200) with a JSON body containing 'token'.  
    """  
    payload = {  
        "mode": "testing",  
        "context": context,  
        "question": question,  
        "incidentNumber": incident_number,  
    }  
    resp = requests.post(ai_endpoint_url, json=payload, headers=headers, timeout=60)  
    resp.raise_for_status()  
    try:  
        data = resp.json()  
    except ValueError:  
        raise ValueError(  
            f"AI Endpoint initial response is not valid JSON: {resp.text}"  
        )  
    token = data.get("token")  
    if not token:  
        raise ValueError(f"AI Endpoint initial response did not include 'token': {data}")  
    return token  
  
  
def poll_ai_endpoint_for_answer(ai_endpoint_url, headers, token):  
    """  
    Poll the AI Endpoint with the given token until a final answer is ready.  
    Returns the final JSON object containing 'aiAnswer' and 'aiRationale'.  
    """  
    while True:  
        payload = {"mode": "polling", "token": token}  
        resp = requests.post(ai_endpoint_url, json=payload, headers=headers, timeout=60)  
        if resp.status_code == 202:  
            print("AI Endpoint still processing... waiting 10 seconds")  
            time.sleep(10)  
            continue  
  
        resp.raise_for_status()  
        try:  
            data = resp.json()  
        except ValueError:  
            raise ValueError(  
                f"AI Endpoint final response is not valid JSON: {resp.text}"  
            )  
        return data  
  
  
def get_ai_answer(ai_endpoint_url, headers, context, question, incident_number):  
    """  
    Full round-trip to the AI Endpoint for a single question.  
    Returns (aiAnswer, aiRationale, full_response, token).  
    """  
    token = submit_question_to_ai_endpoint(  
        ai_endpoint_url, headers, context, question, incident_number  
    )  
    final_data = poll_ai_endpoint_for_answer(ai_endpoint_url, headers, token)  
  
    ai_answer = final_data.get("aiAnswer")  
    ai_rationale = final_data.get("aiRationale")  
  
    if ai_answer is None:  
        print("Warning: AI Endpoint response did not contain 'aiAnswer'. Using empty string.")  
        ai_answer = ""  
    if ai_rationale is None:  
        ai_rationale = ""  
  
    return ai_answer, ai_rationale, final_data, token  
  
  
def save_result(incident_name, test_round_name, results_list, results_filename=None):  
    """  
    Save the current results_list to disk.  
  
    By default the filename is {incident_name}_results.json, but a custom  
    results_filename can be provided (e.g. for retest_x files).  
    """  
    folder_path = os.path.join(RESULTS_DIR, test_round_name)  
    os.makedirs(folder_path, exist_ok=True)  
    if results_filename is None:  
        results_filename = f"{incident_name}_results.json"  
    result_file = os.path.join(folder_path, results_filename)  
    with open(result_file, "w", encoding="utf-8") as f:  
        json.dump(results_list, f, indent=4)  
  
  
def list_result_folders():  
    if not os.path.isdir(RESULTS_DIR):  
        return []  
    folders = [  
        d  
        for d in os.listdir(RESULTS_DIR)  
        if os.path.isdir(os.path.join(RESULTS_DIR, d))  
    ]  
    folders.sort(  
        key=lambda d: os.path.getctime(os.path.join(RESULTS_DIR, d)),  
        reverse=True,  
    )  
    return folders  
  
  
def select_result_folder(purpose="Scoring/Tuning"):  
    while True:  
        folders = list_result_folders()  
        if not folders:  
            print("No test runs found.")  
            return None  
        print(f"\nAvailable Test Runs for {purpose}:")  
        for idx, folder in enumerate(folders, start=1):  
            print(f"{idx}) {folder}")  
        print("0) Back to Main Menu")  
        choice = input("Select a test run: ").strip()  
        if choice == "0":  
            return None  
        try:  
            idx = int(choice)  
            if 1 <= idx <= len(folders):  
                return folders[idx - 1]  
        except ValueError:  
            pass  
        print("Invalid selection. Try again.")  
  
  
def select_results_json_file(folder_path):  
    json_files = [f for f in os.listdir(folder_path) if f.endswith("_results.json")]  
    if not json_files:  
        print(f"No results JSON files found in {folder_path}")  
        return None  
    json_files.sort(  
        key=lambda f: os.path.getctime(os.path.join(folder_path, f)),  
        reverse=True,  
    )  
    while True:  
        print("\nAvailable results files:")  
        for idx, fname in enumerate(json_files, start=1):  
            print(f"{idx}) {fname}")  
        print("0) Back")  
        choice = input("Select a results file: ").strip()  
        if choice == "0":  
            return None  
        try:  
            idx = int(choice)  
            if 1 <= idx <= len(json_files):  
                return json_files[idx - 1]  
        except ValueError:  
            pass  
        print("Invalid selection. Try again.")  
  
  
def get_retest_index_from_results_filename(filename):  
    """  
    Returns the integer retest index encoded in a results filename.  
  
    For filenames like "{incident}_retest_2_results.json" this returns 2.  
    For base filenames like "{incident}_results.json" this returns 0.  
    """  
    match = re.search(r"_retest_(\d+)_results\.json$", filename)  
    if match:  
        return int(match.group(1))  
    return 0  
  
  
def find_base_and_next_retest_indices(folder_path, incident_name):  
    """  
    Within a given test folder, find the 'base' results file (the one with  
    the highest retest index for the given incident) and compute the next  
    retest index to use.  
  
    Returns (base_results_filename, base_retest_index, next_retest_index)  
    or (None, None, None) if no results file is found.  
    """  
    pattern = re.compile(  
        rf"^{re.escape(incident_name)}(?:_retest_(\d+))?_results\.json$"  
    )  
    base_filename = None  
    max_index = -1  
  
    for fname in os.listdir(folder_path):  
        m = pattern.match(fname)  
        if not m:  
            continue  
        if m.group(1):  
            idx = int(m.group(1))  
        else:  
            idx = 0  
        if idx > max_index:  
            max_index = idx  
            base_filename = fname  
  
    if base_filename is None:  
        return None, None, None  
  
    base_retest_index = max_index  
    next_retest_index = base_retest_index + 1  
    return base_filename, base_retest_index, next_retest_index  
  
  
def is_abend(ai_full_response):  
    """  
    Return True if the ai_full_response structure indicates an abend.  
    We look for an 'abend' key with truthy / 1-like value anywhere in the  
    nested structure.  
    """  
    try:  
        if ai_full_response is None:  
            return False  
  
        if isinstance(ai_full_response, str):  
            s = ai_full_response.strip()  
            if not s:  
                return False  
            if s[0] in "{[":  
                try:  
                    parsed = json.loads(s)  
                except Exception:  
                    return False  
                return is_abend(parsed)  
            return False  
  
        if isinstance(ai_full_response, dict):  
            val = ai_full_response.get("abend")  
            if val in (1, "1", True, "true", "True"):  
                return True  
            for v in ai_full_response.values():  
                if is_abend(v):  
                    return True  
            return False  
  
        if isinstance(ai_full_response, list):  
            for v in ai_full_response:  
                if is_abend(v):  
                    return True  
            return False  
  
    except Exception:  
        return False  
  
    return False  
  
  
def run_new_test_for_incident(incident_name):  
    ai_endpoint_url, headers = get_ai_endpoint_config("Testing")  
    questions = load_questions(incident_name)  
    if not questions:  
        return  
  
    total_questions = len(questions)  
    selected_indices = select_test_approach(total_questions)  
    if not selected_indices:  
        print("No questions selected for testing.")  
        return  
  
    if not confirm_start():  
        print("Testing cancelled.")  
        return  
  
    test_round_name = create_test_round_name(incident_name)  
    results_list = []  
  
    total_selected = len(selected_indices)  
    for seq_idx, question_index in enumerate(selected_indices, start=1):  
        if not (0 <= question_index < total_questions):  
            continue  
        q = questions[question_index]  
        test_number = question_index + 1  
  
        print(  
            f"\nProcessing Question {seq_idx}/{total_selected} "  
            f"(test_number={test_number})..."  
        )  
  
        context = q["context"]  
        question = q["question"]  
        incident_number = q.get("incidentNumber", test_number)  
  
        try:  
            ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                ai_endpoint_url, headers, context, question, incident_number  
            )  
  
            new_q = dict(q)  
            new_q["aiAnswer"] = ai_answer  
            new_q["aiRationale"] = ai_rationale  
            new_q["aiFullResponse"] = full_response  
            new_q["test_number"] = test_number  
            new_q["incidentNumber"] = incident_number  
            new_q["retest"] = 0  
  
            results_list.append(new_q)  
            save_result(incident_name, test_round_name, results_list)  
        except Exception as e:  
            print(f"Error processing question with test_number {test_number}: {e}")  
            continue  
  
    print("\nTesting complete. Summary:")  
    print(f"Incident: {incident_name}")  
    print(f"Questions processed: {len(results_list)}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, test_round_name, f'{incident_name}_results.json')}"  
    )  
  
  
def continue_from_last_question(  
    ai_endpoint_url,  
    headers,  
    incident_name,  
    test_round_name,  
    base_results_data,  
    new_results_filename,  
):  
    questions = load_questions(incident_name)  
    if not questions:  
        print("Cannot load questions for incident; aborting restart.")  
        return  
  
    total_questions = len(questions)  
    if total_questions == 0:  
        print("No questions available for this incident.")  
        return  
  
    max_test_num = 0  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if isinstance(tn, int) and tn > 0:  
            if tn > max_test_num:  
                max_test_num = tn  
        else:  
            if idx > max_test_num:  
                max_test_num = idx  
  
    if max_test_num >= total_questions:  
        print("All questions for this incident have already been tested in this run.")  
        return  
  
    start_index = max_test_num  
    indices_to_run = list(range(start_index, total_questions))  
  
    print(  
        f"Continuing test from question {max_test_num + 1} "  
        f"to {total_questions}."  
    )  
  
    new_results_list = []  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
        copied = dict(item)  
        copied["test_number"] = tn  
        copied["retest"] = 0  
        new_results_list.append(copied)  
  
    save_result(  
        incident_name,  
        test_round_name,  
        new_results_list,  
        results_filename=new_results_filename,  
    )  
  
    total_new = len(indices_to_run)  
    for seq_idx, question_index in enumerate(indices_to_run, start=1):  
        q = questions[question_index]  
        test_number = question_index + 1  
        print(  
            f"\nProcessing Question {seq_idx}/{total_new} "  
            f"(test_number={test_number})..."  
        )  
  
        context = q["context"]  
        question = q["question"]  
        incident_number = q.get("incidentNumber", test_number)  
  
        try:  
            ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                ai_endpoint_url, headers, context, question, incident_number  
            )  
  
            new_q = dict(q)  
            new_q["aiAnswer"] = ai_answer  
            new_q["aiRationale"] = ai_rationale  
            new_q["aiFullResponse"] = full_response  
            new_q["test_number"] = test_number  
            new_q["incidentNumber"] = incident_number  
            new_q["retest"] = 1  
  
            new_results_list.append(new_q)  
            save_result(  
                incident_name,  
                test_round_name,  
                new_results_list,  
                results_filename=new_results_filename,  
            )  
        except Exception as e:  
            print(f"Error processing question with test_number {test_number}: {e}")  
            continue  
  
    print("\nRestart (continue) complete. Summary:")  
    print(f"Incident: {incident_name}")  
    print(f"Existing questions carried over: {len(base_results_data)}")  
    print(f"New questions processed: {total_new}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, test_round_name, new_results_filename)}"  
    )  
  
  
def retest_incorrect_answers(  
    ai_endpoint_url,  
    headers,  
    incident_name,  
    test_round_name,  
    base_results_data,  
    scoring_path,  
    new_results_filename,  
):  
    try:  
        with open(scoring_path, "r", encoding="utf-8") as f:  
            scoring_data = json.load(f)  
    except Exception as e:  
        print(f"Error reading scoring file {scoring_path}: {e}")  
        return  
  
    test_numbers_to_retest = set()  
    for idx, entry in enumerate(scoring_data, start=1):  
        result = str(entry.get("result", "")).lower()  
        if result == "incorrect":  
            tn = entry.get("test_number")  
            if isinstance(tn, int) and tn > 0:  
                test_numbers_to_retest.add(tn)  
            else:  
                test_numbers_to_retest.add(idx)  
  
    if not test_numbers_to_retest:  
        print("No incorrect answers found to retest.")  
        return  
  
    print(f"Retesting {len(test_numbers_to_retest)} incorrect answers.")  
  
    new_results_list = []  
    total_questions = len(base_results_data)  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
  
        if tn in test_numbers_to_retest:  
            print(  
                f"\nRetesting Question {idx}/{total_questions} "  
                f"(test_number={tn})..."  
            )  
  
            context = item["context"]  
            question = item["question"]  
            incident_number = item.get("incidentNumber", tn)  
  
            try:  
                ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                    ai_endpoint_url, headers, context, question, incident_number  
                )  
  
                new_entry = dict(item)  
                new_entry["aiAnswer"] = ai_answer  
                new_entry["aiRationale"] = ai_rationale  
                new_entry["aiFullResponse"] = full_response  
                new_entry["test_number"] = tn  
                new_entry["incidentNumber"] = incident_number  
                new_entry["retest"] = 1  
            except Exception as e:  
                print(  
                    f"Error retesting question with test_number {tn}: {e}. "  
                    f"Preserving previous result."  
                )  
                new_entry = dict(item)  
                new_entry["test_number"] = tn  
                new_entry["retest"] = 0  
        else:  
            new_entry = dict(item)  
            new_entry["test_number"] = tn  
            new_entry["retest"] = 0  
  
        new_results_list.append(new_entry)  
        save_result(  
            incident_name,  
            test_round_name,  
            new_results_list,  
            results_filename=new_results_filename,  
        )  
  
    print("\nRetest of incorrect answers complete.")  
    print(f"Incident: {incident_name}")  
    print(f"Questions processed: {len(new_results_list)}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, test_round_name, new_results_filename)}"  
    )  
  
  
def retest_abends(  
    ai_endpoint_url,  
    headers,  
    incident_name,  
    test_round_name,  
    base_results_data,  
    new_results_filename,  
):  
    test_numbers_to_retest = set()  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
        if is_abend(item.get("aiFullResponse")):  
            test_numbers_to_retest.add(tn)  
  
    if not test_numbers_to_retest:  
        print("No abend results found to retest.")  
        return  
  
    print(f"Retesting {len(test_numbers_to_retest)} abend questions.")  
  
    new_results_list = []  
    total_questions = len(base_results_data)  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
  
        if tn in test_numbers_to_retest:  
            print(  
                f"\nRetesting abend Question {idx}/{total_questions} "  
                f"(test_number={tn})..."  
            )  
  
            context = item["context"]  
            question = item["question"]  
            incident_number = item.get("incidentNumber", tn)  
  
            try:  
                ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                    ai_endpoint_url, headers, context, question, incident_number  
                )  
  
                new_entry = dict(item)  
                new_entry["aiAnswer"] = ai_answer  
                new_entry["aiRationale"] = ai_rationale  
                new_entry["aiFullResponse"] = full_response  
                new_entry["test_number"] = tn  
                new_entry["incidentNumber"] = incident_number  
                new_entry["retest"] = 1  
            except Exception as e:  
                print(  
                    f"Error retesting abend question with test_number {tn}: {e}. "  
                    f"Preserving previous result."  
                )  
                new_entry = dict(item)  
                new_entry["test_number"] = tn  
                new_entry["retest"] = 0  
        else:  
            new_entry = dict(item)  
            new_entry["test_number"] = tn  
            new_entry["retest"] = 0  
  
        new_results_list.append(new_entry)  
        save_result(  
            incident_name,  
            test_round_name,  
            new_results_list,  
            results_filename=new_results_filename,  
        )  
  
    print("\nRetest of abend questions complete.")  
    print(f"Incident: {incident_name}")  
    print(f"Questions processed: {len(new_results_list)}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, test_round_name, new_results_filename)}"  
    )  
  
  
def restart_existing_test():  
    folder_name = select_result_folder("Restart")  
    if folder_name is None:  
        return  
  
    incident_name, timestamp = parse_test_round_name(folder_name)  
    if not incident_name or not timestamp:  
        print(  
            "Could not parse incident/timestamp from test folder name: "  
            f"{folder_name}"  
        )  
        return  
  
    folder_path = os.path.join(RESULTS_DIR, folder_name)  
    base_results_filename, base_retest_index, next_retest_index = (  
        find_base_and_next_retest_indices(folder_path, incident_name)  
    )  
  
    if base_results_filename is None:  
        print(f"No results JSON file found in {folder_path}")  
        return  
  
    base_results_path = os.path.join(folder_path, base_results_filename)  
    try:  
        with open(base_results_path, "r", encoding="utf-8") as f:  
            base_results_data = json.load(f)  
    except Exception as e:  
        print(f"Error reading base results file {base_results_filename}: {e}")  
        return  
  
    if not isinstance(base_results_data, list):  
        print(  
            f"Results file {base_results_filename} is not a JSON list; "  
            "cannot restart."  
        )  
        return  
  
    if base_retest_index == 0:  
        scoring_filename = "scoring.json"  
    else:  
        scoring_filename = f"scoring_retest_{base_retest_index}.json"  
  
    scoring_path = os.path.join(folder_path, scoring_filename)  
    has_scoring = os.path.exists(scoring_path)  
    has_abends = any(is_abend(item.get("aiFullResponse")) for item in base_results_data)  
  
    ai_endpoint_url, headers = get_ai_endpoint_config("Restart existing test")  
  
    print(f"\nSelected test folder: {folder_name}")  
    print(f"Incident: {incident_name}")  
    print(f"Test Run Timestamp: {timestamp}")  
    print(f"Base results file: {base_results_filename}")  
    if has_scoring:  
        print(f"Associated scoring file: {scoring_filename}")  
    else:  
        print("No associated scoring file found for this results set.")  
  
    while True:  
        print("\nSelect testing routine:")  
        print("1) Begin where last test stopped")  
        if has_scoring:  
            print("2) Retest all incorrect answers from existing test")  
        else:  
            print(  
                "2) Retest all incorrect answers from existing test "  
                "(requires scoring file - not available)"  
            )  
        print("3) Retest all abends")  
        print("0) Cancel")  
  
        choice = input("Select an option: ").strip()  
        if choice == "0":  
            return  
        if choice == "1":  
            if not confirm_start():  
                print("Restart cancelled.")  
                return  
            new_results_filename = (  
                f"{incident_name}_retest_{next_retest_index}_results.json"  
            )  
            continue_from_last_question(  
                ai_endpoint_url,  
                headers,  
                incident_name,  
                folder_name,  
                base_results_data,  
                new_results_filename,  
            )  
            return  
        if choice == "2":  
            if not has_scoring:  
                print(  
                    "Cannot retest incorrect answers because the scoring file "  
                    "is missing."  
                )  
                continue  
            if not confirm_start():  
                print("Retest cancelled.")  
                return  
            new_results_filename = (  
                f"{incident_name}_retest_{next_retest_index}_results.json"  
            )  
            retest_incorrect_answers(  
                ai_endpoint_url,  
                headers,  
                incident_name,  
                folder_name,  
                base_results_data,  
                scoring_path,  
                new_results_filename,  
            )  
            return  
        if choice == "3":  
            if not has_abends:  
                print("No abend results found in this test; nothing to retest.")  
                return  
            if not confirm_start():  
                print("Retest cancelled.")  
                return  
            new_results_filename = (  
                f"{incident_name}_retest_{next_retest_index}_results.json"  
            )  
            retest_abends(  
                ai_endpoint_url,  
                headers,  
                incident_name,  
                folder_name,  
                base_results_data,  
                new_results_filename,  
            )  
            return  
        print("Invalid selection. Try again.")  
  
  
def resume_test_mode():  
    print("\n=== Resume Test Mode ===")  
    folder_name = select_result_folder("Resume")  
    if folder_name is None:  
        return  
  
    incident_name, timestamp = parse_test_round_name(folder_name)  
    if not incident_name or not timestamp:  
        print(f"Could not parse incident/timestamp from test folder name: {folder_name}")  
        return  
  
    folder_path = os.path.join(RESULTS_DIR, folder_name)  
    results_filename = select_results_json_file(folder_path)  
    if results_filename is None:  
        return  
  
    results_path = os.path.join(folder_path, results_filename)  
    try:  
        with open(results_path, "r", encoding="utf-8") as f:  
            results_data = json.load(f)  
    except Exception as e:  
        print(f"Error reading results file {results_filename}: {e}")  
        return  
  
    if not isinstance(results_data, list):  
        print(f"Results file {results_filename} is not a JSON list; cannot resume.")  
        return  
  
    questions = load_questions(incident_name)  
    if not questions:  
        print("Cannot load questions for incident; aborting resume.")  
        return  
    total_questions = len(questions)  
    if total_questions == 0:  
        print("No questions available for this incident.")  
        return  
  
    normalized = [None] * total_questions  
    for idx, item in enumerate(results_data, start=1):  
        if not isinstance(item, dict):  
            continue  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0 or tn > total_questions:  
            tn = idx  
        if 1 <= tn <= total_questions and normalized[tn - 1] is None:  
            normalized[tn - 1] = item  
  
    remaining_indices = [i for i in range(total_questions) if normalized[i] is None]  
    if not remaining_indices:  
        print("All questions already have results in this file. Nothing to resume.")  
        return  
  
    retest_default = 0  
    for item in reversed(results_data):  
        if isinstance(item, dict) and "retest" in item:  
            try:  
                retest_default = int(item["retest"])  
            except Exception:  
                retest_default = 0  
            break  
  
    ai_endpoint_url, headers = get_ai_endpoint_config("Resume test")  
  
    print(f"\nSelected test folder: {folder_name}")  
    print(f"Incident: {incident_name}")  
    print(f"Test Run Timestamp: {timestamp}")  
    print(f"Results file to resume: {results_filename}")  
    print(f"Detected {len(results_data)} existing entries.")  
    print(f"Next unprocessed test_number: {remaining_indices[0] + 1}")  
    print(f"Will process remaining {len(remaining_indices)} question(s).")  
  
    if not confirm_start():  
        print("Resume cancelled.")  
        return  
  
    results_list = list(results_data)  
    total_new = len(remaining_indices)  
  
    for seq_idx, question_index in enumerate(remaining_indices, start=1):  
        q = questions[question_index]  
        test_number = question_index + 1  
        print(  
            f"\nProcessing Question {seq_idx}/{total_new} "  
            f"(test_number={test_number})..."  
        )  
  
        context = q["context"]  
        question = q["question"]  
        incident_number = q.get("incidentNumber", test_number)  
  
        try:  
            ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                ai_endpoint_url, headers, context, question, incident_number  
            )  
  
            new_q = dict(q)  
            new_q["aiAnswer"] = ai_answer  
            new_q["aiRationale"] = ai_rationale  
            new_q["aiFullResponse"] = full_response  
            new_q["test_number"] = test_number  
            new_q["incidentNumber"] = incident_number  
            new_q["retest"] = retest_default  
  
            results_list.append(new_q)  
            save_result(  
                incident_name,  
                folder_name,  
                results_list,  
                results_filename=results_filename,  
            )  
        except Exception as e:  
            print(f"Error processing question with test_number {test_number}: {e}")  
            continue  
  
    print("\nResume complete. Summary:")  
    print(f"Incident: {incident_name}")  
    print(f"New questions processed: {len(results_list) - len(results_data)}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, folder_name, results_filename)}"  
    )  
  
  
def score_results():  
    ai_endpoint_url, headers = get_ai_endpoint_config("Scoring")  
  
    folder_name = select_result_folder("Scoring")  
    if folder_name is None:  
        return  
  
    folder_path = os.path.join(RESULTS_DIR, folder_name)  
    results_filename = select_results_json_file(folder_path)  
    if results_filename is None:  
        return  
  
    if not confirm_start():  
        print("Scoring cancelled.")  
        return  
  
    results_file = os.path.join(folder_path, results_filename)  
    try:  
        with open(results_file, "r", encoding="utf-8") as f:  
            results_data = json.load(f)  
    except Exception as e:  
        print(f"Error reading results file {results_filename}: {e}")  
        return  
  
    if not isinstance(results_data, list):  
        print(f"Results file {results_filename} is not a JSON list; cannot score.")  
        return  
  
    retest_index = get_retest_index_from_results_filename(results_filename)  
    if retest_index == 0:  
        scoring_filename = "scoring.json"  
    else:  
        scoring_filename = f"scoring_retest_{retest_index}.json"  
    scoring_file_path = os.path.join(folder_path, scoring_filename)  
  
    scoring_results = []  
    correct_count = 0  
  
    for idx, item in enumerate(results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
  
        print(  
            f"\nScoring Question {idx}/{len(results_data)} "  
            f"(test_number={tn})..."  
        )  
  
        payload = {  
            "mode": "scoring",  
            "context": item.get("context", ""),  
            "question": item.get("question", ""),  
            "answerKey": item.get("answer", ""),  
            "aiAnswer": item.get("aiAnswer", ""),  
            "aiRationale": item.get("aiRationale", ""),  
        }  
  
        try:  
            resp = requests.post(  
                ai_endpoint_url, json=payload, headers=headers, timeout=60  
            )  
            resp.raise_for_status()  
            data = resp.json()  
  
            result_str = str(data.get("result", "")).strip().lower()  
            is_correct = result_str == "correct"  
  
            result_entry = {  
                "test_number": tn,  
                "incidentNumber": item.get("incidentNumber", tn),  
                "context": item.get("context", ""),  
                "question": item.get("question", ""),  
                "answer": item.get("answer", ""),  
                "aiAnswer": item.get("aiAnswer", ""),  
                "aiRationale": item.get("aiRationale", ""),  
                "result": data.get("result", ""),  
                "score": data.get("score"),  
                "scoringRationale": data.get("scoringRationale"),  
                "aiScoringFullResponse": data,  
            }  
            if "retest" in item:  
                result_entry["retest"] = item["retest"]  
  
            if is_correct:  
                correct_count += 1  
  
            scoring_results.append(result_entry)  
            with open(scoring_file_path, "w", encoding="utf-8") as sf:  
                json.dump(scoring_results, sf, indent=4)  
        except Exception as e:  
            print(f"Error scoring question {idx}: {e}")  
            continue  
  
    percentage_correct = (  
        (correct_count / len(results_data)) * 100 if results_data else 0  
    )  
    print(  
        f"\nScoring complete. {correct_count}/{len(results_data)} correct "  
        f"({percentage_correct:.2f}%)."  
    )  
    print(f"Scoring results saved to: {scoring_file_path}")  
  
  
def parse_comma_separated_test_numbers(s):  
    """  
    Parse a comma-separated list of integers (e.g., '1, 4, 7') and return a set of ints.  
    Invalid tokens are ignored.  
    """  
    nums = set()  
    for tok in s.split(","):  
        tok = tok.strip()  
        if not tok:  
            continue  
        try:  
            n = int(tok)  
            if n > 0:  
                nums.add(n)  
        except ValueError:  
            continue  
    return nums  
  
  
def retest_individual_items():  
    print("\n=== Retest Individual Items (Select Specific Test Numbers) ===")  
    folder_name = select_result_folder("Retesting")  
    if folder_name is None:  
        return  
  
    incident_name, timestamp = parse_test_round_name(folder_name)  
    if not incident_name or not timestamp:  
        print(  
            "Could not parse incident/timestamp from test folder name: "  
            f"{folder_name}"  
        )  
        return  
  
    folder_path = os.path.join(RESULTS_DIR, folder_name)  
    results_filename = select_results_json_file(folder_path)  
    if results_filename is None:  
        return  
  
    base_results_path = os.path.join(folder_path, results_filename)  
    try:  
        with open(base_results_path, "r", encoding="utf-8") as f:  
            base_results_data = json.load(f)  
    except Exception as e:  
        print(f"Error reading results file {results_filename}: {e}")  
        return  
  
    if not isinstance(base_results_data, list):  
        print(f"Results file {results_filename} is not a JSON list; cannot retest.")  
        return  
  
    available_test_numbers = set()  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
        available_test_numbers.add(tn)  
  
    print(f"Available test numbers in this file: {sorted(available_test_numbers)}")  
    raw = input("Enter comma-separated test numbers to retest (e.g., 1,3,7): ").strip()  
    requested = parse_comma_separated_test_numbers(raw)  
    selected = sorted(requested.intersection(available_test_numbers))  
    if not selected:  
        print("No valid test numbers selected. Retesting cancelled.")  
        return  
  
    ai_endpoint_url, headers = get_ai_endpoint_config("Retest individual items")  
  
    base_results_filename, base_retest_index, next_retest_index = (  
        find_base_and_next_retest_indices(folder_path, incident_name)  
    )  
    if base_results_filename is None:  
        print(f"No results JSON files found in {folder_path}")  
        return  
    new_results_filename = f"{incident_name}_retest_{next_retest_index}_results.json"  
  
    print(f"\nSelected test folder: {folder_name}")  
    print(f"Incident: {incident_name}")  
    print(f"Test Run Timestamp: {timestamp}")  
    print(f"Base results file: {results_filename}")  
    print(f"Will retest test_number(s): {selected}")  
    if not confirm_start():  
        print("Retesting cancelled.")  
        return  
  
    new_results_list = []  
    total_questions = len(base_results_data)  
  
    for idx, item in enumerate(base_results_data, start=1):  
        tn = item.get("test_number")  
        if not isinstance(tn, int) or tn <= 0:  
            tn = idx  
  
        if tn in selected:  
            print(  
                f"\nRetesting selected Question {idx}/{total_questions} "  
                f"(test_number={tn})..."  
            )  
  
            context = item["context"]  
            question = item["question"]  
            incident_number = item.get("incidentNumber", tn)  
  
            try:  
                ai_answer, ai_rationale, full_response, _token = get_ai_answer(  
                    ai_endpoint_url, headers, context, question, incident_number  
                )  
  
                new_entry = dict(item)  
                new_entry["aiAnswer"] = ai_answer  
                new_entry["aiRationale"] = ai_rationale  
                new_entry["aiFullResponse"] = full_response  
                new_entry["test_number"] = tn  
                new_entry["incidentNumber"] = incident_number  
                new_entry["retest"] = 1  
            except Exception as e:  
                print(  
                    f"Error retesting selected question with test_number {tn}: {e}. "  
                    f"Preserving previous result."  
                )  
                new_entry = dict(item)  
                new_entry["test_number"] = tn  
                new_entry["retest"] = 0  
        else:  
            new_entry = dict(item)  
            new_entry["test_number"] = tn  
            new_entry["retest"] = 0  
  
        new_results_list.append(new_entry)  
        save_result(  
            incident_name,  
            folder_name,  
            new_results_list,  
            results_filename=new_results_filename,  
        )  
  
    print("\nRetesting (selected) complete. Summary:")  
    print(f"Incident: {incident_name}")  
    print(f"Questions processed: {len(new_results_list)}")  
    print(  
        "Results saved in: "  
        f"{os.path.join(RESULTS_DIR, folder_name, new_results_filename)}"  
    )  
  
  
def run_testing():  
    while True:  
        incidents = list_incidents()  
        if not incidents:  
            print("No incidents found.")  
            return  
  
        print("\nAvailable Incidents for Testing:")  
        for idx, incident in enumerate(incidents, start=1):  
            print(f"{idx}) {incident}")  
        print("R) Restart existing test")  
        print("I) Retest Individual Items")  
        print("0) Back to Main Menu")  
  
        choice = input("Select an incident or option: ").strip()  
        if choice == "0":  
            return  
        if choice.upper() == "R":  
            restart_existing_test()  
            return  
        if choice.upper() == "I":  
            retest_individual_items()  
            return  
        try:  
            idx = int(choice)  
            if 1 <= idx <= len(incidents):  
                incident_name = incidents[idx - 1]  
                run_new_test_for_incident(incident_name)  
                return  
        except ValueError:  
            pass  
        print("Invalid selection. Try again.")  
  
  
def main():  
    welcome_message()  
    while True:  
        choice = main_menu()  
        if choice == "1":  
            run_testing()  
        elif choice == "2":  
            score_results()  
        elif choice == "3":  
            show_help()  
        elif choice == "0":  
            print("Exiting...")  
            break  
        else:  
            print("Invalid selection.")  
  
  
if __name__ == "__main__":  
    main()  