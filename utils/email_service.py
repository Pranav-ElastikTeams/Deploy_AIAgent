import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_APP_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))


def send_ethics_complaint_email(to_email: str, complainant: str, complaint_data: dict):
    msg = EmailMessage()
    msg['Subject'] = f"Complaint Logged: {complaint_data['Complaint ID']}"
    msg['From'] = f"Ethics Case Screener <{EMAIL_ADDRESS}>"
    msg['To'] = to_email

    # Create the email body in HTML format
    body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 650px; margin: 0 auto; color: #333; line-height: 1.6;">
        
        <!-- Header Section -->
        <div style="background: linear-gradient(135deg, #2c3e50, #34495e); color: white; padding: 30px 25px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0; font-size: 24px; font-weight: 300;">Ethics Complaint Acknowledgment</h2>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">Case Management System</p>
        </div>
        
        <!-- Main Content -->
        <div style="background: #ffffff; padding: 30px 25px; border: 1px solid #e1e8ed; border-top: none;">
            <p style="margin-top: 0; font-size: 16px; color: #2c3e50;">Dear {complainant},</p>

            <p style="color: #555; font-size: 15px; margin-bottom: 25px;">
                Thank you for bringing this matter to our attention. We take all ethics concerns seriously and are committed to ensuring a thorough and confidential review process. Your complaint has been successfully registered in our system with the details outlined below.
            </p>

            <!-- Case Details Card -->
            <div style="background: #f8f9fc; border: 1px solid #e1e8ed; border-radius: 6px; padding: 20px; margin: 25px 0;">
                <h3 style="margin: 0 0 15px 0; color: #2c3e50; font-size: 18px; font-weight: 500; border-bottom: 2px solid #3498db; padding-bottom: 8px;">Case Details</h3>
                
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; width: 30%; vertical-align: top;">Complaint ID:</td>
                        <td style="padding: 12px 0; color: #555; font-family: 'Courier New', monospace; font-weight: 500; background: #fff; padding-left: 10px; border-radius: 3px;">{complaint_data['Complaint ID']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Type:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data['Complaint Type']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Subject:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data.get('Victim Name', '')} (Victim), {complaint_data.get('Suspect Name', '')} (Suspect)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Date Submitted:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data['Date']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Description:</td>
                        <td style="padding: 12px 0; color: #555; line-height: 1.5;">{complaint_data['Description']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Supporting Evidence:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data['Evidence']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Assigned Investigator:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data['Assigned To']}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Victim Name:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data.get('Victim Name', '')}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Suspect Name:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data.get('Suspect Name', '')}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e8ecf0;">
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Relation:</td>
                        <td style="padding: 12px 0; color: #555;">{complaint_data.get('Relation', '')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 15px 12px 0; font-weight: 600; color: #2c3e50; vertical-align: top;">Current Status:</td>
                        <td style="padding: 12px 0;">
                            <span style="background: #e8f5e8; color: #2d5a2d; padding: 4px 12px; border-radius: 15px; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">
                                {complaint_data['Status']}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>

            <!-- Next Steps Section -->
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 20px; margin: 25px 0;">
                <h4 style="margin: 0 0 10px 0; color: #b8860b; font-size: 16px; display: flex; align-items: center;">
                    <span style="background: #ffd700; width: 20px; height: 20px; border-radius: 50%; display: inline-block; margin-right: 10px; text-align: center; line-height: 20px; font-size: 12px;">!</span>
                    Next Steps
                </h4>
                <p style="margin: 0; color: #856404; font-size: 14px; line-height: 1.5;">
                    A dedicated member of our Ethics Review Committee will contact you within <strong>5 business days</strong> to discuss the investigation process and any additional information that may be required. Please retain this complaint ID for your records.
                </p>
            </div>

            <!-- Contact Information -->
            <div style="border-top: 1px solid #e1e8ed; padding-top: 20px; margin-top: 30px;">
                <p style="color: #555; font-size: 14px; margin-bottom: 15px;">
                    <strong>Questions or Additional Information?</strong><br>
                    If you need to provide supplementary information or have questions about this case, please contact our Ethics Hotline at <strong>ethics@company.com</strong> and reference your complaint ID.
                </p>
                
                <p style="color: #555; font-size: 14px; margin-bottom: 0;">
                    We appreciate your commitment to maintaining the highest ethical standards within our organization.
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background: #f8f9fc; padding: 20px 25px; border: 1px solid #e1e8ed; border-top: none; border-radius: 0 0 8px 8px; text-align: center;">
            <p style="margin: 0; color: #6c757d; font-size: 14px;">
                <strong>Ethics Case Management Team</strong><br>
                <span style="font-size: 12px; opacity: 0.8;">Confidential & Secure Processing</span>
            </p>
        </div>
        
    </div>
    """


    msg.set_content("This email contains HTML content. Please use an HTML-compatible viewer.")
    msg.add_alternative(body, subtype='html')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print(f"Email sent to {to_email} successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")
