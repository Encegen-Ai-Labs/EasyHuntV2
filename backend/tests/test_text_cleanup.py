from app.services.text_cleanup import clean_page_text


def test_none_and_empty_pass_through():
    assert clean_page_text(None) is None
    assert clean_page_text("") == ""


def test_br_outside_a_table_becomes_a_line_break():
    assert clean_page_text("Plot 12<br>Village Wagholi<BR/>Pune") == "Plot 12\nVillage Wagholi\nPune"


def test_stray_pipes_outside_a_table_are_removed():
    assert clean_page_text("Owner | Ramesh Patil\nसही | ") == "Owner Ramesh Patil\nसही"


def test_real_table_is_kept_and_br_inside_cells_becomes_a_space():
    text = "| Survey | Owner |\n| --- | --- |\n| 12/3 | Ramesh<br>Patil |"
    assert clean_page_text(text) == "| Survey | Owner |\n| --- | --- |\n| 12/3 | Ramesh Patil |"


def test_br_that_splits_a_row_is_rejoined():
    text = "| Survey | Owner |\n| --- | --- |\n| 12/3 | Ramesh<br> Patil |"
    assert clean_page_text(text).splitlines()[-1] == "| 12/3 | Ramesh Patil |"


def test_two_unrelated_pipe_lines_are_not_a_table():
    cleaned = clean_page_text("a | b | c\nonly | one")
    assert "|" not in cleaned


def test_prose_around_a_table_is_cleaned_independently():
    text = "Heading | x\n| A | B |\n| - | - |\n| 1 | 2 |\nfooter<br>line"
    assert clean_page_text(text) == "Heading x\n| A | B |\n| - | - |\n| 1 | 2 |\nfooter\nline"


def test_cleaning_is_idempotent():
    text = "| A | B |\n| --- | --- |\n| 1<br>2 | 3 |\nplain | text<br>more"
    once = clean_page_text(text)
    assert clean_page_text(once) == once


def test_devanagari_danda_is_untouched():
    assert clean_page_text("हे खरे आहे ।") == "हे खरे आहे ।"


def test_split_blocks_separates_prose_and_tables():
    from app.services.text_cleanup import split_blocks

    text = "Intro line\n| Survey | Owner |\n| --- | --- |\n| 12/3 | Ramesh |\n| 12/4 | Suresh |\nOutro"
    assert split_blocks(text) == [
        {"type": "text", "text": "Intro line"},
        {"type": "table", "columns": ["Survey", "Owner"], "rows": [["12/3", "Ramesh"], ["12/4", "Suresh"]]},
        {"type": "text", "text": "Outro"},
    ]


def test_split_blocks_with_no_table_is_one_text_block():
    from app.services.text_cleanup import split_blocks

    assert split_blocks("a\nb") == [{"type": "text", "text": "a\nb"}]
    assert split_blocks("") == []
