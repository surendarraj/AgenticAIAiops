FROM python:3.11-slim
WORKDIR /app
COPY agents /app/agents
COPY service.py /app/service.py
RUN pip install --no-cache-dir fastapi uvicorn pyyaml kubernetes langchain langgraph "pydantic>=2,<3" numpy scipy statsmodels langchain-openai openai
EXPOSE 8080
ENTRYPOINT ["uvicorn","service:app","--host","0.0.0.0","--port","8080"]
