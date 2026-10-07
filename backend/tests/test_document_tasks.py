from app.tasks import document_tasks


def test_document_task_runs_the_existing_pipeline(monkeypatch):
    class StubPipeline:
        def execute_analysis_pipeline(self, document_id):
            assert document_id == "document-123"
            return {"status": "success"}

    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: StubPipeline())

    result = document_tasks.process_document_task.run("document-123")

    assert result == {"document_id": "document-123", "status": "success"}
