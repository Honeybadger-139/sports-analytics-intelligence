# Learning Note: Hybrid Serverless Deployment (Vercel + Cloud Run)

## What is it?
A deployment architecture where the frontend (React/Vite) is hosted on a static edge network (like Vercel) while the backend API (Python/FastAPI) is hosted on a separate serverless container platform (like Google Cloud Run). 

## Why does it matter?
Historically, applications were deployed as "monoliths" on a single server (like an AWS EC2 instance). This meant the server had to process API requests, serve HTML files, and handle database queries all at once. If your frontend got popular, your backend slowed down.

By decoupling the frontend and backend, we map the workload to the best possible infrastructure:
1. **Frontend (Vercel):** Static files (HTML/CSS/JS) are cached on a global CDN (Content Delivery Network). This means a user in Tokyo downloads the UI from a server in Tokyo, while a user in London downloads it from London. Load times are near zero.
2. **Backend (Cloud Run):** Python ML code is heavy. Google Cloud Run automatically spins up Docker containers to handle incoming API traffic. If traffic spikes, it creates more containers. If traffic drops to zero, it scales to zero containers (meaning you pay nothing).

## How does it work (Intuition)?
Think of a high-end restaurant:
- **Vercel is the Front-of-House (The Setup):** The tables, menus, and decor are pre-arranged and identical for every customer. Customers get seated instantly.
- **Cloud Run is the Kitchen (The Backend):** When an order (API request) comes in, the chefs (containers) fire up to cook the meal (run the ML model or database query). If 100 orders come in at once, management temporarily hires more chefs (auto-scaling). 

## When to use vs alternatives?
| Architecture | Best For | Trade-offs |
|--------------|----------|------------|
| **Hybrid Serverless (Vercel + Cloud Run)** | Modern decoupling. Heavy backend workloads (ML, Python) paired with fast React UIs. | Requires configuring CORS. Slightly more complex deployment pipeline. |
| **Monolith (AWS EC2 / DigitalOcean)** | Simple apps, legacy systems, or specific hardware needs (always-on GPUs). | Paying for idle time. Harder to scale automatically. |
| **Full Stack Next.js (Vercel only)** | Pure Javascript/TypeScript apps where the API logic is simple. | Cannot easily run heavy Python ML libraries (PyTorch, XGBoost) natively in Vercel. |

## 👔 The Senior Manager Perspective
*"In our organization, we optimize for two things: Developer Velocity and Cost-to-Serve. I chose a Vercel/Cloud Run architecture because it gives us continuous deployment out-of-the-box. Developers merge to main, and the infrastructure automatically builds and serves the traffic globally. Furthermore, by utilizing scale-to-zero serverless containers for our heavy machine learning endpoints, we eliminate the wasteful idle costs associated with traditional VMs while ensuring we can handle sudden bursts of viral traffic."*

---

## 🎤 Interview Angles

**Question:** "Why didn't you just deploy both your React frontend and your Python backend on a single AWS EC2 instance?"
**Junior Answer:** "Because I know how to use Vercel and it's easy, and Cloud Run is cool."
**Senior/Architect Answer:** "I explicitly chose a decoupled serverless architecture. Hosting static React assets on a traditional VM is an anti-pattern because you lose the latency benefits of a global edge CDN. By separating them, the frontend achieves sub-100ms time-to-interactive globally via Vercel's edge network. For the Python FastAPI backend, which requires ML libraries and database connections, Cloud Run allows us to scale stateless containers horizontally based on concurrency, while preserving scale-to-zero capabilities for cost efficiency."

**Question:** "What challenges did you face when splitting the frontend and backend?"
**Senior/Architect Answer:** "The main challenge is Cross-Origin Resource Sharing (CORS). Because Vercel and Cloud Run operate on different domains, the browser's security model blocks API requests by default. I had to explicitly configure the FastAPI CORS middleware to accept pre-flight `OPTIONS` requests and allow specific origins (or `*` during development/initial deploy) so the frontend could successfully retrieve the data."
