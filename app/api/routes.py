import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
import io

from app.models.schemas import (
    QueryRequest, AnalysisTypeCreate, AnalysisTypeUpdate,
    EmailRequest, ApiKeyCreate, ApiQueryRequest,
)
from app.core.database import get_sync_connection, get_all_tables, execute_readonly_sql
from app.core.security import validate_api_key, create_api_key
from app.core.config import settings
from app.services.excel_service import import_excel
from app.services.agent_service import run_query, reset_agent
from app.services.email_service import send_email_with_excel, export_to_excel_bytes

router = APIRouter(prefix="/api")


# --- Tables ---

@router.get("/tables")
async def list_tables():
    return get_all_tables()


@router.get("/tables/{table_name}/preview")
async def preview_table(table_name: str, limit: int = Query(20, le=100)):
    result = execute_readonly_sql(f'SELECT * FROM "{table_name}" LIMIT {limit}')
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# --- Excel Upload ---

@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Apenas arquivos Excel (.xlsx, .xls) são aceitos.")

    dest = settings.upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        report = import_excel(dest)
        reset_agent()  # Schema changed, rebuild agent
        return {"filename": file.filename, "sheets": report}
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar Excel: {str(e)}")


# --- Query (Natural Language) ---

@router.post("/query")
async def query_nl(req: QueryRequest):
    try:
        result = await run_query(
            question=req.question,
            analysis_type_id=req.analysis_type_id,
            context=req.conversation_context,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Erro na consulta: {str(e)}")


# --- Direct SQL ---

@router.post("/sql")
async def run_sql(sql: str):
    result = execute_readonly_sql(sql)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# --- Analysis Types (System Prompts & Guardrails) ---

@router.get("/analysis-types")
async def list_analysis_types():
    conn = get_sync_connection()
    try:
        cursor = conn.execute("SELECT * FROM analysis_types ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


@router.get("/analysis-types/{type_id}")
async def get_analysis_type(type_id: int):
    conn = get_sync_connection()
    try:
        cursor = conn.execute("SELECT * FROM analysis_types WHERE id = ?", (type_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Tipo de análise não encontrado.")
        return dict(row)
    finally:
        conn.close()


@router.post("/analysis-types")
async def create_analysis_type(data: AnalysisTypeCreate):
    conn = get_sync_connection()
    try:
        conn.execute(
            "INSERT INTO analysis_types (name, system_prompt, guardrails_input, guardrails_output) VALUES (?, ?, ?, ?)",
            (data.name, data.system_prompt, data.guardrails_input, data.guardrails_output),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.put("/analysis-types/{type_id}")
async def update_analysis_type(type_id: int, data: AnalysisTypeUpdate):
    conn = get_sync_connection()
    try:
        fields = []
        values = []
        for field_name in ("name", "system_prompt", "guardrails_input", "guardrails_output"):
            val = getattr(data, field_name)
            if val is not None:
                fields.append(f"{field_name} = ?")
                values.append(val)
        if not fields:
            raise HTTPException(400, "Nenhum campo para atualizar.")
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(type_id)
        conn.execute(
            f"UPDATE analysis_types SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@router.delete("/analysis-types/{type_id}")
async def delete_analysis_type(type_id: int):
    conn = get_sync_connection()
    try:
        conn.execute("DELETE FROM analysis_types WHERE id = ?", (type_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


# --- Export Excel ---

@router.post("/export/excel")
async def export_excel(data: dict):
    excel_bytes = export_to_excel_bytes(data)
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=data_insights_export.xlsx"},
    )


# --- Email ---

@router.post("/email")
async def send_email(req: EmailRequest):
    result = send_email_with_excel(
        to_email=req.to_email,
        subject=req.subject,
        body_html=req.body_html,
        data=req.excel_data,
    )
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


# --- API Keys ---

@router.post("/keys")
async def create_key(data: ApiKeyCreate):
    result = create_api_key(data.label)
    return result


@router.get("/keys")
async def list_keys():
    conn = get_sync_connection()
    try:
        cursor = conn.execute("SELECT id, label, is_active, created_at FROM api_keys ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# --- External API (with API Key auth) ---

@router.post("/v1/query")
async def external_query(req: ApiQueryRequest, x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(401, "API key inválida ou inativa.")
    try:
        result = await run_query(
            question=req.question,
            analysis_type_id=req.analysis_type_id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Erro na consulta: {str(e)}")


# --- Query History ---

@router.get("/history")
async def query_history(limit: int = Query(20, le=100)):
    conn = get_sync_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM query_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
