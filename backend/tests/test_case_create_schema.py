from app.schemas.cases import CaseCreate


def test_case_create_does_not_require_a_survey_number():
    case = CaseCreate(property_name="Parcel 12")

    assert case.property_name == "Parcel 12"
    assert case.survey_number is None
