# 🚀 HireMind

### AI-Powered Job Discovery, Matching & Application Assistant

HireMind is a modular AI-powered platform designed to streamline the job-search workflow.

It brings together **job discovery, multi-source ingestion, job normalization, intelligent matching, AI-powered processing, Gmail integration, and a unified web dashboard** into a single system.

Instead of manually searching multiple platforms, evaluating every opportunity, and managing application-related emails separately, HireMind aims to turn the process into a structured workflow:

> **Discover → Normalize → Match → Analyze → Draft → Track**

---

## ✨ What is HireMind?

Job hunting often involves repetitive work:

* Searching across multiple job platforms
* Reading hundreds of job descriptions
* Comparing jobs with your skills and resume
* Identifying relevant opportunities
* Managing recruitment emails
* Preparing application responses
* Keeping track of opportunities

HireMind is built to automate and organize these parts of the workflow.

The project uses a **service-oriented architecture**, allowing job ingestion, AI processing, matching, Gmail integration, and the frontend to evolve independently.

---

# 🧠 Core Capabilities

## 🔎 Multi-Source Job Ingestion

HireMind provides a dedicated ingestion service for collecting opportunities from multiple job platforms.

Current ingestion sources include:

* **Internshala**
* **LinkedIn**
* **Unstop**

Each source has its own implementation while the shared ingestion layer provides common functionality such as normalization and source management.

```text
Job Sources
     │
     ├── Internshala
     ├── LinkedIn
     └── Unstop
             │
             ▼
      Ingestion Service
             │
             ▼
       Normalized Jobs
```

---

## 🎯 Intelligent Job Matching

Collected jobs are processed through the matching layer to determine their relevance to the user's profile and resume.

The matching system is separated into the shared matching module so that matching logic can evolve independently from the ingestion pipeline.

This creates a foundation for:

* Skill matching
* Resume-to-job comparison
* Job relevance scoring
* Personalized job recommendations

---

## 🤖 AI / LLM Integration

HireMind supports multiple LLM providers through a shared abstraction layer.

Currently supported providers include:

* **Groq**
* **Anthropic / Claude**

The LLM layer is designed so application components don't need to be tightly coupled to a single AI provider.

The LLM functionality is used for tasks including:

* Gmail importance classification
* Resume-driven job search keyword generation
* AI-powered processing within the intelligence layer

Provider selection is controlled through:

```env
LLM_PROVIDER=groq
```

---

## 📧 Gmail Integration

HireMind includes Gmail integration for handling application-related email workflows.

The Gmail module provides functionality for:

* OAuth authentication
* Email fetching
* Email classification
* Processing recruitment-related messages
* Draft management
* Pushing drafts

This creates the foundation for connecting job discovery with the communication side of the application process.

---

## 🖥️ Web Dashboard

The frontend is built using **React and Vite**.

The dashboard currently contains dedicated interfaces for:

* 📥 Inbox
* 🎯 Matches
* ✍️ Drafts

The dashboard communicates with the backend through the gateway layer rather than directly coupling the frontend to individual services.

---

# 🏗️ Architecture

HireMind follows a modular service-oriented architecture.

```text
                         ┌──────────────────────┐
                         │      Dashboard       │
                         │      React + Vite    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Gateway Service    │
                         │      API Layer       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌────────────────┐ ┌───────────────┐ ┌────────────────┐
          │   Ingestion    │ │ Intelligence  │ │ Shared Modules │
          │    Service     │ │    Service    │ │                │
          │                │ │               │ │ DB / Gmail     │
          │ Job Sources    │ │ AI / Matching │ │ LLM / Ingestion│
          └───────┬────────┘ └───────┬───────┘ │ Matching       │
                  │                  │           └───────┬────────┘
                  └──────────────────┼──────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │    Database     │
                            │                 │
                            │ SQLAlchemy      │
                            │ + Alembic       │
                            └─────────────────┘
```

### Service responsibilities

| Component              | Responsibility                           |
| ---------------------- | ---------------------------------------- |
| `dashboard`            | React web interface                      |
| `gateway-service`      | Backend API entry point                  |
| `ingestion-service`    | Collects jobs from external sources      |
| `intelligence-service` | AI-powered processing                    |
| `shared/db`            | Database models, sessions and migrations |
| `shared/ingestion`     | Common ingestion and normalization       |
| `shared/matching`      | Job matching logic                       |
| `shared/llm`           | LLM provider abstraction                 |
| `shared/gmail`         | Gmail integration                        |
| `shared/generation`    | Resume/content generation utilities      |

---

# 🔄 End-to-End Workflow

A typical HireMind workflow looks like this:

```text
                    ┌─────────────────┐
                    │   Job Sources   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Ingestion    │
                    │     Service     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Normalize     │
                    │    Job Data     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Matching Engine │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Intelligence /  │
                    │   LLM Layer     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Dashboard    │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                 Matches            Drafts
                                      │
                                      ▼
                                    Gmail
```

---

# 📁 Project Structure

```text
HireMind/
│
├── dashboard/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── styles/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── main.jsx
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   └── env.example
│
├── gateway-service/
│   ├── app/
│   │   ├── main.py
│   │   └── schemas.py
│   ├── requirements.txt
│   └── env.example
│
├── ingestion-service/
│   ├── app/
│   │   ├── main.py
│   │   └── sources/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── env.example
│
├── intelligence-service/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   ├── resume.txt
│   └── env.example
│
├── shared/
│   ├── db/
│   │   ├── alembic/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── alembic.ini
│   │
│   ├── generation/
│   │   ├── generator.py
│   │   └── resume_store.py
│   │
│   ├── gmail/
│   │   ├── auth.py
│   │   ├── classify.py
│   │   ├── fetch.py
│   │   └── push.py
│   │
│   ├── ingestion/
│   │   ├── common.py
│   │   ├── normalize.py
│   │   ├── registry.py
│   │   └── sources/
│   │
│   ├── llm/
│   │   ├── client.py
│   │   ├── groq_client.py
│   │   └── claude_client.py
│   │
│   └── matching/
│       └── matcher.py
│
├── run_gateway.py
├── run_ingestion.py
├── run_matching.py
│
├── .gitignore
└── README.md
```

---

# 🛠️ Tech Stack

### Frontend

* React
* Vite
* JavaScript
* CSS

### Backend

* Python
* Modular service architecture

### Database

* PostgreSQL
* SQLAlchemy
* Alembic

### AI

* Groq
* Anthropic Claude
* LLM provider abstraction

### Data Ingestion

* Python
* Internshala
* LinkedIn
* Unstop
* Source normalization layer

### Integrations

* Gmail OAuth
* Gmail API
* Firecrawl

### Development

* Git
* GitHub
* Docker

---

# ⚙️ Getting Started

## Prerequisites

Make sure you have installed:

* Python 3.13+
* Node.js
* npm
* PostgreSQL
* Git

---

## 1. Clone the repository

```bash
git clone https://github.com/Bhardwaj-Nishant/HireMind.git
cd HireMind
```

---

# 2. Configure the Database

HireMind uses PostgreSQL.

For local development, the expected database configuration is:

```env
DATABASE_URL=postgresql+psycopg2://hiremind:hiremind@localhost:5432/hiremind
```

Create the database before starting the backend services.

---

# 3. Configure Environment Variables

Each service contains an `env.example` file.

Create your local environment configuration from the example.

For example:

```text
ingestion-service/
├── env.example
├── client_secrets.json
└── ...
```

### Example configuration

```env
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

DATABASE_URL=postgresql+psycopg2://hiremind:hiremind@localhost:5432/hiremind

INTERNSHALA_REQUEST_DELAY=2
UNSTOP_REQUEST_DELAY=2

LINKEDIN_LI_AT=your_li_at_cookie_value
LINKEDIN_JSESSIONID=your_jsessionid_cookie_value

LINKEDIN_MIN_INTERVAL_HOURS=1
LINKEDIN_REQUEST_DELAY=2

GOOGLE_CLIENT_SECRETS_PATH=./client_secrets.json

LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-5

RESUME_PATH=../intelligence-service/resume.txt
```

### 🔐 Important

**Never commit real credentials to GitHub.**

The following must remain local:

```text
.env
client_secrets.json
```

Use `env.example` files with placeholder values when sharing the project.

---

# 4. Google Gmail OAuth

Gmail functionality requires a Google OAuth client configuration.

Place the credentials locally at:

```text
ingestion-service/client_secrets.json
```

Configure:

```env
GOOGLE_CLIENT_SECRETS_PATH=./client_secrets.json
```

The actual credentials file should **never be committed to Git**.

The project `.gitignore` should contain:

```gitignore
.env
.env.*
client_secrets.json
**/client_secrets.json
```

---

# 5. Install Python Dependencies

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
```

Install dependencies for the required services:

```bash
pip install -r gateway-service/requirements.txt
pip install -r ingestion-service/requirements.txt
pip install -r intelligence-service/requirements.txt
```

Shared database dependencies can also be installed with:

```bash
pip install -r shared/db/requirements.txt
```

---

# 6. Install Dashboard Dependencies

```bash
cd dashboard
npm install
```

Start the development server:

```bash
npm run dev
```

---

# 7. Run the Services

From the project root:

### Gateway

```bash
python run_gateway.py
```

### Ingestion

```bash
python run_ingestion.py
```

### Matching

```bash
python run_matching.py
```

The dashboard can be started separately with:

```bash
cd dashboard
npm run dev
```

---

# 🗄️ Database Migrations

HireMind uses **Alembic** for database schema migrations.

Migration files are located at:

```text
shared/db/alembic/versions/
```

To apply migrations:

```bash
alembic upgrade head
```

---

# 🔐 Security & Credentials

HireMind integrates with several external services that require credentials.

These credentials should **never** be committed to source control.

### Never commit:

```text
.env
client_secrets.json
API keys
OAuth secrets
LinkedIn session cookies
Database passwords
```

### Safe to commit:

```text
env.example
package.json
package-lock.json
requirements.txt
source code
database migration files
README.md
```

---

# 🧩 Design Principles

HireMind is built around a few architectural principles.

### Separation of concerns

Each service owns a specific responsibility instead of putting the entire application into one backend.

### Shared abstractions

Common functionality such as:

* Database access
* LLM providers
* Gmail integration
* Ingestion
* Matching

is centralized under `shared/`.

### Provider flexibility

The LLM layer abstracts provider-specific implementations:

```text
              ┌──────────────┐
              │  LLM Client  │
              └───────┬──────┘
                      │
             ┌────────┴────────┐
             ▼                 ▼
       ┌───────────┐     ┌───────────┐
       │   Groq    │     │ Anthropic │
       └───────────┘     └───────────┘
```

This allows the application to switch providers through configuration rather than rewriting the rest of the application.

---

# 🚧 Current Limitations

HireMind is an actively developed project.

Some integrations rely on third-party services and unofficial interfaces. In particular, LinkedIn ingestion uses a session-cookie-based approach and therefore depends on the continued availability and behavior of the external platform.

External APIs, authentication flows, rate limits, and scraping restrictions may change over time.

---

# 🗺️ Roadmap

* [ ] Expand job-source integrations
* [ ] Improve semantic job matching
* [ ] Improve relevance scoring
* [ ] Add richer job recommendations
* [ ] Enhance AI-generated application drafts
* [ ] Improve Gmail classification
* [ ] Add application status tracking
* [ ] Add automated testing
* [ ] Add CI/CD
* [ ] Add production deployment configuration
* [ ] Add service monitoring and observability
* [ ] Improve background job processing
* [ ] Improve dashboard analytics

---

# 🎯 Vision

HireMind aims to transform job searching from a repetitive browsing task into an intelligent workflow.

```text
┌───────────┐
│ Discover  │
└─────┬─────┘
      ▼
┌───────────┐
│ Normalize │
└─────┬─────┘
      ▼
┌───────────┐
│   Match   │
└─────┬─────┘
      ▼
┌───────────┐
│  Analyze  │
└─────┬─────┘
      ▼
┌───────────┐
│   Draft   │
└─────┬─────┘
      ▼
┌───────────┐
│   Apply   │
└─────┬─────┘
      ▼
┌───────────┐
│   Track   │
└───────────┘
```

The long-term goal is to create a single intelligent workspace where users can discover relevant opportunities, understand their fit, manage applications, and organize recruitment communication.

---

# 👨‍💻 Author

### Nishant Bhardwaj

B.Tech Computer Science & Engineering

GitHub: https://github.com/Bhardwaj-Nishant

LinkedIn: https://www.linkedin.com/in/nishant-bhardwaj-7b15b7333/

---

# ⭐ Contributing

Contributions and suggestions are welcome.

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature/your-feature
```

3. Make your changes
4. Commit your changes

```bash
git commit -m "Add your feature"
```

5. Push the branch

```bash
git push origin feature/your-feature
```

6. Open a Pull Request

---

# 📄 License

License information will be added as the project moves toward public release.
