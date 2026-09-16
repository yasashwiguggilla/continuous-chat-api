import azure.functions as func
import json
import os
from datetime import datetime, timezone

from azure.storage.blob import BlobServiceClient
from openai import OpenAI


# ============================================================
# FUNCTION APP
# ============================================================

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.ANONYMOUS
)


# ============================================================
# STUDENT STORAGE
# ============================================================

student_connection_string = os.environ["AzureWebJobsStorage"]

student_blob_service_client = BlobServiceClient.from_connection_string(
    student_connection_string
)

student_container_client = (
    student_blob_service_client.get_container_client("students")
)

student_blob_client = (
    student_container_client.get_blob_client("students.json")
)


def read_students():
    data = student_blob_client.download_blob().readall()
    return json.loads(data)


def write_students(students):
    data = json.dumps(students, indent=2)

    student_blob_client.upload_blob(
        data,
        overwrite=True
    )


# ============================================================
# STUDENT APIs
# ============================================================

@app.route(
    route="students",
    methods=["GET"]
)
def get_students(req: func.HttpRequest) -> func.HttpResponse:

    try:
        students = read_students()

        return func.HttpResponse(
            json.dumps(students),
            status_code=200,
            mimetype="application/json"
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to read students"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="students/{student_id}",
    methods=["GET"]
)
def get_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = req.route_params.get("student_id")

        students = read_students()

        for student in students:
            if str(student.get("id")) == str(student_id):

                return func.HttpResponse(
                    json.dumps(student),
                    status_code=200,
                    mimetype="application/json"
                )

        return func.HttpResponse(
            json.dumps({
                "error": "Student not found"
            }),
            status_code=404,
            mimetype="application/json"
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to retrieve student"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="students",
    methods=["POST"]
)
def create_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        body = req.get_json()

        students = read_students()

        students.append(body)

        write_students(students)

        return func.HttpResponse(
            json.dumps(body),
            status_code=201,
            mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "Invalid JSON"
            }),
            status_code=400,
            mimetype="application/json"
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to create student"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="students/{student_id}",
    methods=["PUT"]
)
def update_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = req.route_params.get("student_id")

        body = req.get_json()

        students = read_students()

        for index, student in enumerate(students):

            if str(student.get("id")) == str(student_id):

                students[index] = body

                write_students(students)

                return func.HttpResponse(
                    json.dumps(body),
                    status_code=200,
                    mimetype="application/json"
                )

        return func.HttpResponse(
            json.dumps({
                "error": "Student not found"
            }),
            status_code=404,
            mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "Invalid JSON"
            }),
            status_code=400,
            mimetype="application/json"
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to update student"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="students/{student_id}",
    methods=["DELETE"]
)
def delete_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = req.route_params.get("student_id")

        students = read_students()

        for index, student in enumerate(students):

            if str(student.get("id")) == str(student_id):

                deleted_student = students.pop(index)

                write_students(students)

                return func.HttpResponse(
                    json.dumps({
                        "message": "Student deleted successfully",
                        "student": deleted_student
                    }),
                    status_code=200,
                    mimetype="application/json"
                )

        return func.HttpResponse(
            json.dumps({
                "error": "Student not found"
            }),
            status_code=404,
            mimetype="application/json"
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to delete student"
            }),
            status_code=500,
            mimetype="application/json"
        )


# ============================================================
# GROQ CLIENT
# ============================================================

groq_client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
)


# ============================================================
# CHAT BLOB STORAGE
# ============================================================

chat_connection_string = os.environ[
    "CHAT_STORAGE_CONNECTION_STRING"
]

chat_blob_service_client = BlobServiceClient.from_connection_string(
    chat_connection_string
)

chat_container_client = (
    chat_blob_service_client.get_container_client("chat-history")
)


def read_conversation(session_id):

    blob_client = chat_container_client.get_blob_client(
        f"{session_id}.json"
    )

    try:
        data = blob_client.download_blob().readall()

        return json.loads(data)

    except Exception:
        return {
            "session_id": session_id,
            "messages": []
        }


def save_conversation(session_id, conversation):

    blob_client = chat_container_client.get_blob_client(
        f"{session_id}.json"
    )

    data = json.dumps(
        conversation,
        indent=2
    )

    blob_client.upload_blob(
        data,
        overwrite=True
    )


# ============================================================
# CONTINUOUS CHAT API
# ============================================================

@app.route(
    route="chat",
    methods=["POST"]
)
def chat(req: func.HttpRequest) -> func.HttpResponse:

    # ========================================================
    # REQUEST JSON VALIDATION
    # ========================================================

    try:
        body = req.get_json()

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "Request body must be valid JSON"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # ========================================================
    # GET INPUTS
    # ========================================================

    session_id = body.get("session_id")
    message = body.get("message")

    # ========================================================
    # SESSION ID VALIDATION
    # ========================================================

    if not session_id or not isinstance(session_id, str):
        return func.HttpResponse(
            json.dumps({
                "error": "session_id is required and must be a string"
            }),
            status_code=400,
            mimetype="application/json"
        )

    session_id = session_id.strip()

    if not session_id:
        return func.HttpResponse(
            json.dumps({
                "error": "session_id cannot be empty"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # ========================================================
    # MESSAGE VALIDATION
    # ========================================================

    if not message or not isinstance(message, str):
        return func.HttpResponse(
            json.dumps({
                "error": "message is required and must be a string"
            }),
            status_code=400,
            mimetype="application/json"
        )

    message = message.strip()

    if not message:
        return func.HttpResponse(
            json.dumps({
                "error": "message cannot be empty"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # ========================================================
    # MESSAGE LENGTH VALIDATION
    # ========================================================

    if len(message) > 4000:
        return func.HttpResponse(
            json.dumps({
                "error": "message cannot exceed 4000 characters"
            }),
            status_code=400,
            mimetype="application/json"
        )

    # ========================================================
    # READ CONVERSATION FROM BLOB
    # ========================================================

    try:
        conversation = read_conversation(session_id)

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to read conversation history from Blob Storage"
            }),
            status_code=500,
            mimetype="application/json"
        )

    # ========================================================
    # ADD USER MESSAGE
    # ========================================================

    conversation["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    })

    # ========================================================
    # KEEP COMPLETE HISTORY IN BLOB
    #
    # BUT SEND ONLY LATEST 20 MESSAGES TO GROQ
    # ========================================================

    recent_messages = conversation["messages"][-20:]

    # ========================================================
    # CALL GROQ
    # ========================================================

    try:

        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in recent_messages
            ]
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to get response from AI service"
            }),
            status_code=502,
            mimetype="application/json"
        )

    # ========================================================
    # GET AI RESPONSE
    # ========================================================

    answer = response.choices[0].message.content

    # ========================================================
    # ADD AI RESPONSE TO COMPLETE HISTORY
    # ========================================================

    conversation["messages"].append({
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    })

    # ========================================================
    # SAVE COMPLETE CONVERSATION TO BLOB
    # ========================================================

    try:

        save_conversation(
            session_id,
            conversation
        )

    except Exception:
        return func.HttpResponse(
            json.dumps({
                "error": "AI response generated, but conversation could not be saved"
            }),
            status_code=500,
            mimetype="application/json"
        )

    # ========================================================
    # SUCCESS RESPONSE
    # ========================================================

    return func.HttpResponse(
        json.dumps({
            "session_id": session_id,
            "message": message,
            "response": answer,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }),
        status_code=200,
        mimetype="application/json"
    )