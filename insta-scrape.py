import os

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from instagrapi import Client
import time
import csv
import uuid

app = FastAPI()

# store progress
tasks = {}

# -----------------------
# SCRAPER FUNCTION
# -----------------------
def scrape_instagram(task_id, session_id, target_username):
    cl = Client()
    cl.set_delay_range([2, 5])
    cl.login_by_sessionid(session_id)

    user_id = cl.user_id_from_username(target_username)
    following = cl.user_following(user_id)

    total = len(following)
    data = []

    tasks[task_id]["total"] = total

    for i, user in enumerate(following.values(), start=1):
        try:
            info = cl.user_info(user.pk)

            data.append({
                "Name": info.full_name,
                "Phone Number": info.public_phone_number,
                "Email": info.public_email,
                "Website": info.external_url,
                "Instagram": info.username,
                "No. of Followers": info.follower_count,
                "Country": "",
                "Alt Web": "",
                "Comments": info.biography
            })

        except Exception as e:
            print(f"Error: {e}")

        tasks[task_id]["progress"] = i
        time.sleep(2)

    filename = f"{target_username}_{task_id}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        if not data:
            tasks[task_id]["status"] = "error"
            return

        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    tasks[task_id]["status"] = "done"
    tasks[task_id]["file"] = filename


# -----------------------
# UI PAGE
# -----------------------
@app.get("/", response_class=HTMLResponse)
def form_page():
    return """
    <html>
    <head>
        <title>Instagram Scraper</title>
    </head>
    <body>
        <h2>Instagram Scraper</h2>

        <form id="form">
            Session ID:<br>
            <input type="text" id="session_id" style="width:400px;"><br><br>

            Username:<br>
            <input type="text" id="username"><br><br>

            <button type="submit">Start</button>
        </form>

        <br>
        <div id="status"></div>
        <progress id="progress" value="0" max="100" style="width:400px;"></progress>

        <script>
        document.getElementById("form").onsubmit = async (e) => {
            e.preventDefault();

            const session_id = document.getElementById("session_id").value;
            const username = document.getElementById("username").value;

            let res = await fetch("/start", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({session_id, username})
            });

            let data = await res.json();
            let task_id = data.task_id;

            checkProgress(task_id);
        };

        async function checkProgress(task_id) {
            let interval = setInterval(async () => {
                let res = await fetch(`/progress/${task_id}`);
                let data = await res.json();

                if (data.total > 0) {
                    let percent = (data.progress / data.total) * 100;
                    document.getElementById("progress").value = percent;
                    document.getElementById("status").innerText =
                        `${data.progress} / ${data.total}`;
                }

                if (data.status === "done") {
                    clearInterval(interval);
                    document.getElementById("status").innerHTML =
                        `Done! <a href="/download/${task_id}">Download CSV</a>`;
                }

                if (data.status === "error") {
                    clearInterval(interval);
                    document.getElementById("status").innerText = "Error during scraping";
                }
            }, 1000);
        }
        </script>
    </body>
    </html>
    """


# -----------------------
# START TASK
# -----------------------
@app.post("/start")
async def start_task(request: dict):
    if "session_id" not in request or "username" not in request:
        return {"error": "Missing input"}

    if not request["session_id"] or not request["username"]:
        return {"error": "Empty values"}

    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "progress": 0,
        "total": 0,
        "status": "running",
        "file": None
    }

    import threading
    threading.Thread(
        target=scrape_instagram,
        args=(task_id, request["session_id"], request["username"]),
        daemon=True
    ).start()   

    return {"task_id": task_id}


# -----------------------
# CHECK PROGRESS
# -----------------------
@app.get("/progress/{task_id}")
def get_progress(task_id: str):
    return tasks.get(task_id, {})


# -----------------------
# DOWNLOAD
# -----------------------
@app.get("/download/{task_id}")
def download(task_id: str):
    task = tasks.get(task_id)

    if not task or not task.get("file"):
        return {"error": "File not ready"}

    return FileResponse(task["file"], filename=task["file"])


if __name__ == "__insta-scrape__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("insta-scrape:app", host="0.0.0.0", port=port)