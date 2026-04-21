This project runs a Streamlit-based pro forma planner inside a Docker container.

## Prerequisites

Install [Docker](https://www.docker.com/get-started).

## Build the Docker Image

From the project root, run:

```bash
docker build -t proforma-planner .
```

## Run the Container

Start the app with:

```bash
docker run -d -p 50053:50053 --name proforma-planner proforma-planner
```

## Access the App

Once the container is running, open:

`http://localhost:50053`

## Development Tips

For local development with a mounted source tree:

```bash
docker run -p 50053:50053 -v $(pwd):/app proforma-planner streamlit run main.py --server.address 0.0.0.0 --server.port 50053
```

## Notes

- The container serves the Streamlit UI on port `50053`.
- The app now uses a local mathematical decision engine instead of the old API/OpenAI flow.

## Troubleshooting

Check container logs with:

```bash
docker logs proforma-planner
```
