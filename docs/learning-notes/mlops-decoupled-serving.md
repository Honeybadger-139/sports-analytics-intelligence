# Decoupled Inference (TF Serving & Vertex AI)

## What is it?
Decoupled inference is the architectural pattern of moving your Machine Learning model *out* of your main web application (like Django or FastAPI) and hosting it as a standalone microservice purely dedicated to fast predictions. 
We implemented this by exporting our TensorFlow Wide & Deep model as a `SavedModel` and targeting either a local **TF Serving** Docker container or a **Google Cloud Vertex AI Endpoint**.

## Why does it matter?
Junior data scientists load `model.pkl` or `model.keras` directly inside their Flask or FastAPI APIs. This creates a monolithic application.
1. **Conflicting Scaling Needs**: A web server handles thousands of concurrent I/O requests and scales best on cheap, multi-core CPUs. A Deep Learning model does heavy matrix multiplication and scales best on GPUs. 
2. **Memory Bloat**: Loading a 2GB model file 10 times across 10 Uvicorn worker processes consumes 20GB of RAM unnecessarily.
3. **Dependency Hell**: Forcing your web server to install `tensorflow`, `xgboost`, and `CUDA` bloats the container image dangerously.

Decoupling solves this. FastAPI becomes a lightweight router that makes an HTTP/gRPC call to a dedicated ML Endpoint.

## How does it work (Intuition)?
Instead of:
`User -> FastAPI (Loads Model into RAM, calculates, responds) -> User`

It becomes:
`User -> FastAPI (Lightweight)` 
`FastAPI -> Google Vertex AI Endpoint (Dedicated hardware to run the math)`
`Vertex AI -> FastAPI -> User`

The ML microservice has zero knowledge of your users, sessions, or databases. It just receives an array of numbers and returns a probability.

## 🎤 Common Interview Questions

**Q: In your sports analytics project, how do you handle bursts in web traffic affecting your predictive models?**
*Senior Answer*: "I decoupled the web tier from the inference tier. The React frontend talks to a FastAPI backend deployed on Cloud Run, which handles scaling for high-concurrent web requests. But FastAPI doesn't load the massive TensorFlow model into memory. Instead, it serialises the feature vector into JSON and fires an HTTP POST request to a Google Cloud Vertex AI Endpoint. Because they are decoupled, if there's a huge spike in web traffic just checking scores, my API scales out horizontally on cheap CPUs, but my expensive GPU inference nodes on Vertex AI remain unaffected unless actually invoked."

**Q: How do you deploy your TensorFlow models? Do you just use Flask?**
*Senior Answer*: "No, putting Keras instances inside a Python WSGI/ASGI worker is an anti-pattern for large models due to the Global Interpreter Lock (GIL) and process-level memory duplication. I export my model as a `SavedModel` and serve it using TensorFlow Serving (which is what Vertex AI runs under the hood). TF Serving is written in C++, handles request batching automatically, and provides high-throughput gRPC and REST APIs out of the box."
