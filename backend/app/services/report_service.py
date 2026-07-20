import io
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.repositories.case_repo import CaseRepository
from app.repositories.report_repo import ReportRepository
from app.core.exceptions import ResourceNotFoundError

class ReportGenerationService:
    def __init__(self, case_repo: CaseRepository, report_repo: ReportRepository):
        self.case_repo = case_repo
        self.report_repo = report_repo

    def generate_pdf_report(self, case_id: str, user_id: str) -> Dict[str, Any]:
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Case not found")

        # Compile PDF layout in memory using ReportLab
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=letter,
            rightMargin=40, 
            leftMargin=40, 
            topMargin=40, 
            bottomMargin=40
        )
        story = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=15
        )
        body_style = styles['Normal']
        
        # Document Content Elements
        story.append(Paragraph("PROPERTY OWNERSHIP VERIFICATION REPORT", title_style))
        story.append(Spacer(1, 15))
        
        # Case Details Metadata Table
        data = [
            ["Case Identifier:", str(case_obj["id"])],
            ["Property Address:", case_obj["property_address"]],
            ["Survey Number Ref:", case_obj["survey_number"]],
            ["System Status:", case_obj["status"].upper()]
        ]
        
        summary_table = Table(data, colWidths=[150, 350])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#1F2937')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 25))
        story.append(Paragraph("This document certifies verification workflow analysis of the real estate asset referenced above.", body_style))
        
        doc.build(story)
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        # Save generated document directly to Supabase storage bucket
        storage_path = f"reports/{case_id}/verification_report.pdf"
        self.report_repo.client.storage.from_("reports").upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "x-upsert": "true"}
        )

        report_payload = {
            "case_id": case_id,
            "generated_by": user_id,
            "file_path": storage_path
        }
        return self.report_repo.create_report(report_payload)