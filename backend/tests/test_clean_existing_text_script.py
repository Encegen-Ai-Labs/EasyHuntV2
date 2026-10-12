from scripts.clean_existing_text import run


class _Query:
    def __init__(self, store, table):
        self.store, self.table = store, table
        self._update = None
        self._range = None

    def select(self, _columns):
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def update(self, payload):
        self._update = payload
        return self

    def eq(self, _col, value):
        self._eq = value
        return self

    def execute(self):
        rows = self.store[self.table]
        if self._update is not None:
            for row in rows:
                if row["id"] == self._eq:
                    row.update(self._update)
            return type("R", (), {"data": []})()
        start, end = self._range
        return type("R", (), {"data": [dict(r) for r in rows[start:end + 1]]})()


class _Client:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _Query(self.store, name)


def _store():
    return {
        "document_pages": [
            {"id": "p1", "original_text": "Plot 12<br>Pune | x", "english_text": None},
            {"id": "p2", "original_text": "clean text", "english_text": "also clean"},
        ],
        "extractions": [
            {"id": "e1", "validated_json_output": {"full_text": "a | b<br>c", "owner_name": "X"}},
            {"id": "e2", "validated_json_output": {"owner_name": "Y"}},
        ],
    }


def test_dry_run_counts_but_writes_nothing():
    store = _store()
    counts = run(_Client(store), apply=False)
    assert counts == {"pages_changed": 1, "extractions_changed": 1}
    assert store["document_pages"][0]["original_text"] == "Plot 12<br>Pune | x"


def test_apply_writes_cleaned_text_and_keeps_other_fields():
    store = _store()
    run(_Client(store), apply=True)
    assert store["document_pages"][0]["original_text"] == "Plot 12\nPune x"
    assert store["extractions"][0]["validated_json_output"] == {"full_text": "a b\nc", "owner_name": "X"}
    assert run(_Client(store), apply=False) == {"pages_changed": 0, "extractions_changed": 0}
