import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SENDER_EMAIL, APP_PASSWORD


def send_otp_email(to_email: str, otp: str, purpose: str = "verify"):
    """
    purpose: "verify" | "login" | "reset"
    """

    if purpose == "verify":
        subject = "✅ Verify Your Account — AI Assistant"
        heading = "Welcome! Verify Your Email"
        body_line = "You've just signed up for <b>AI Assistant</b>. Use the OTP below to verify your account:"
        note = "This OTP is valid for <b>10 minutes</b>. If you didn't sign up, please ignore this email."
    elif purpose == "login":
        subject = "🔐 Your Login OTP — AI Assistant"
        heading = "Login OTP"
        body_line = "Use the OTP below to log in to your <b>AI Assistant</b> account:"
        note = "This OTP is valid for <b>10 minutes</b>. If you didn't request this, please ignore."
    else:  # reset
        subject = "🔑 Reset Your Password — AI Assistant"
        heading = "Reset Your Password"
        body_line = "We received a request to reset your password. Use the OTP below:"
        note = "This OTP is valid for <b>10 minutes</b>. If you didn't request a reset, please ignore."

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6fb; font-family:'Segoe UI', Arial, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6fb; padding: 40px 0;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#ffffff; border-radius:16px;
                      box-shadow:0 4px 24px rgba(0,0,0,0.08); overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       padding: 36px 40px; text-align:center;">
              <div style="font-size:36px; margin-bottom:8px;">🤖</div>
              <h1 style="color:#ffffff; margin:0; font-size:22px;
                         font-weight:700; letter-spacing:0.5px;">AI Assistant</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding: 36px 40px;">
              <h2 style="color:#1a1a2e; font-size:20px; margin:0 0 12px 0;">{heading}</h2>
              <p style="color:#555; font-size:15px; line-height:1.6; margin:0 0 28px 0;">
                {body_line}
              </p>

              <!-- OTP Box -->
              <div style="text-align:center; margin: 0 0 28px 0;">
                <div style="display:inline-block; background:#f0f4ff;
                            border: 2px dashed #667eea; border-radius:12px;
                            padding: 18px 48px;">
                  <span style="font-size:38px; font-weight:800;
                               letter-spacing:10px; color:#667eea;
                               font-family:'Courier New', monospace;">
                    {otp}
                  </span>
                </div>
              </div>

              <p style="color:#888; font-size:13px; line-height:1.6;
                        margin:0 0 8px 0; text-align:center;">
                {note}
              </p>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding: 0 40px;">
              <hr style="border:none; border-top:1px solid #eee; margin:0;">
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 40px; text-align:center;">
              <p style="color:#aaa; font-size:12px; margin:0;">
                © 2025 AI Assistant &nbsp;|&nbsp; Do not reply to this email
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>

</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"AI Assistant <{SENDER_EMAIL}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

