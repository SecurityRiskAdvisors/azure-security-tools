chrome.tabs.query({ active: true }).then((tabs) => getUrl(tabs));

function getUrl(tabs) {
  const div = document.createElement('div');
  
  // Process Current URL
  const url = String(tabs[0].url);
  
  div.innerHTML = "<br>Hunt Request Submitted for " + url + "<br>";
  
  // Insert our new html into the page
  var container_block = document.getElementById( 'sracontent' );
  container_block.appendChild( div );

  copilot_hunt_url = "insert-your-logic-app-trigger-url-here";
  const data = { "url": url, "email":"insertyouremailhere" };
  fetch(copilot_hunt_url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
    })
    .catch((error) => {
        console.error("Error:", error);
    });
    
    console.log("requested hunt of " + tab);

}