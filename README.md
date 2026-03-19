This project runs a FastAPI server inside a Docker container. Follow the steps below to build and run the application locally.

---

## 📦 Prerequisites

Make sure you have the following installed:

* [Docker](https://www.docker.com/get-started)

---

## 🏗️ Build the Docker Image

Navigate to the root directory of this project (where the `Dockerfile` is located), then run:

```bash
docker build -t proforma-api .
```

---

## ▶️ Run the Container

Start the FastAPI server in a Docker container:

```bash
docker run -d -p 50053:50053 \
  -e OPENAI_API_KEY=your_api_key_here \
  --name proforma-api \
  proforma-api
```

---

## 🌐 Access the API

Once the container is running, you can access:

* API root: http://localhost:50053
* Interactive docs (Swagger UI): http://localhost:50053/docs


## 🔐 Environment Variables

This project requires an OpenAI API key.

You can pass it using:

```bash
-e OPENAI_API_KEY=your_api_key_here
```

Alternatively, use a `.env` file:

```bash
docker run --env-file .env -p 50053:50053 fastapi-app
```

---

## ⚠️ Notes

* Do **not** commit your `.env` file or API keys to GitHub
* The server runs on port `50053` inside the container
* Make sure the port is not already in use on your machine

## 🚀 Development Tips

If you want live-reload during development:

```bash
docker run -p 50053:50053 -v $(pwd):/app fastapi-app \
uvicorn main:app --host 0.0.0.0 --port 50053 --reload
```

---

## 📬 Questions

If you run into issues, check logs first:

```bash
docker logs fastapi-container
```

---
