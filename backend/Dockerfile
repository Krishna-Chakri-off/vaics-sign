FROM python:3.12-slim
# LibreOffice converts DOCX/XLSX/PPTX uploads to PDF (set INSTALL_LIBREOFFICE=false for a smaller image; PDFs only then).
ARG INSTALL_LIBREOFFICE=true
RUN if [ "$INSTALL_LIBREOFFICE" = "true" ]; then apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress fonts-dejavu && rm -rf /var/lib/apt/lists/*; fi
RUN useradd -m -u 10001 vaics
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=vaics:vaics . .
USER vaics
ENV AUTO_CREATE_TABLES=false
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
