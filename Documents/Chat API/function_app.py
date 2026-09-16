import azure.functions as func
import json
import os

from azure.storage.blob import BlobServiceClient
from openai import OpenAI


app = func.FunctionApp(
    http_auth_level=func.AuthLevel.ANONYMOUS
)


# ==================================================
# STUDENT PERFORMANCE - BLOB STORAGE
# ==================================================

connection_string = os.environ["AzureWebJobsStorage"]

blob_service_client = BlobServiceClient.from_connection_string(
    connection_string
)

student_container_client = blob_service_client.get_container_client(
    "students"
)

student_blob_client = student_container_client.get_blob_client(
    "students.json"
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


# ==================================================
# POST - CREATE STUDENT
# ==================================================

@app.route(route="students", methods=["POST"])
def create_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()

        students = read_students()

        if students:
            new_id = max(
                student["id"] for student in students
            ) + 1
        else:
            new_id = 1

        student = {
            "id": new_id,
            "name": data["name"],
            "age": data["age"],
            "marks": data["marks"],
            "attendance": data["attendance"]
        }

        students.append(student)

        write_students(students)

        return func.HttpResponse(
            json.dumps({
                "message": "Student created successfully",
                "student": student
            }),
            status_code=201,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=400,
            mimetype="application/json"
        )


# ==================================================
# GET - GET ALL STUDENTS
# ==================================================

@app.route(route="students", methods=["GET"])
def get_students(req: func.HttpRequest) -> func.HttpResponse:

    try:
        students = read_students()

        return func.HttpResponse(
            json.dumps({
                "students": students
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )


# ==================================================
# GET - GET STUDENT BY ID
# ==================================================

@app.route(route="students/{student_id}", methods=["GET"])
def get_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = int(
            req.route_params.get("student_id")
        )

        students = read_students()

        for student in students:

            if student["id"] == student_id:

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

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=400,
            mimetype="application/json"
        )


# ==================================================
# PUT - UPDATE STUDENT
# ==================================================

@app.route(route="students/{student_id}", methods=["PUT"])
def update_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = int(
            req.route_params.get("student_id")
        )

        students = read_students()

        data = req.get_json()

        for student in students:

            if student["id"] == student_id:

                student["name"] = data["name"]
                student["age"] = data["age"]
                student["marks"] = data["marks"]
                student["attendance"] = data["attendance"]

                write_students(students)

                return func.HttpResponse(
                    json.dumps({
                        "message": "Student updated successfully",
                        "student": student
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

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=400,
            mimetype="application/json"
        )


# ==================================================
# DELETE - DELETE STUDENT
# ==================================================

@app.route(route="students/{student_id}", methods=["DELETE"])
def delete_student(req: func.HttpRequest) -> func.HttpResponse:

    try:
        student_id = int(
            req.route_params.get("student_id")
        )

        students = read_students()

        for student in students:

            if student["id"] == student_id:

                students.remove(student)

                write_students(students)

                return func.HttpResponse(
                    json.dumps({
                        "message": "Student deleted successfully",
                        "student": student
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

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=400,
            mimetype="application/json"
        )


# ==================================================
# GROQ AI CLIENT
# ==================================================

groq_client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
)


# ==================================================
# CHAT HISTORY - BLOB STORAGE
# ==================================================

chat_connection_string = os.environ[
    "CHAT_STORAGE_CONNECTION_STRING"
]

chat_blob_service_client = BlobServiceClient.from_connection_string(
    chat_connection_string
)

chat_container_client = chat_blob_service_client.get_container_client(
    "chat-history"
)


# ==================================================
# READ CHAT CONVERSATION
# ==================================================

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


# ==================================================
# SAVE CHAT CONVERSATION
# ==================================================

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


# ==================================================
# POST - CONTINUOUS CHAT API
# ==================================================

@app.route(route="chat", methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:

    try:

        # Get request body
        body = req.get_json()

        session_id = body.get("session_id")
        message = body.get("message")

        # Validate input
        if not session_id or not message:

            return func.HttpResponse(
                json.dumps({
                    "error": "session_id and message are required"
                }),
                status_code=400,
                mimetype="application/json"
            )

        # ------------------------------------------
        # Read previous conversation
        # ------------------------------------------

        conversation = read_conversation(
            session_id
        )

        # ------------------------------------------
        # Add user message
        # ------------------------------------------

        conversation["messages"].append({
            "role": "user",
            "content": message
        })

        # ------------------------------------------
        # Send complete conversation to Groq
        # ------------------------------------------

        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=conversation["messages"]
        )

        # ------------------------------------------
        # Get AI response
        # ------------------------------------------

        answer = response.choices[0].message.content

        # ------------------------------------------
        # Add AI response to history
        # ------------------------------------------

        conversation["messages"].append({
            "role": "assistant",
            "content": answer
        })

        # ------------------------------------------
        # Save conversation to Blob
        # ------------------------------------------

        save_conversation(
            session_id,
            conversation
        )

        # ------------------------------------------
        # Return response
        # ------------------------------------------

        return func.HttpResponse(
            json.dumps({
                "session_id": session_id,
                "response": answer
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:

        return func.HttpResponse(
            json.dumps({
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )