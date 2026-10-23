"""Minimal server-side i18n for emails/SMS (en, hi). Add languages by extending MESSAGES; missing keys fall back to English."""
MESSAGES = {
    "en": {
        "email.open": "Review document",
        "email.footer": "This is an automated message from {product}. Do not share this email.",
        "invite.subject": "{sender} requests your signature: {title}",
        "invite.body": "Hello {name},\n\n{sender} has requested your {action} on \"{title}\"{step}.\n{message}\nUse the secure link below.{auth_note}\n\nThis link expires on {expires}.",
        "invite.auth_note": " You will receive your access code separately.",
        "code.subject": "Your access code for \"{title}\"",
        "code.body": "Hello {name},\n\nYour access code for \"{title}\" is below. It expires in {hours} hours and allows {attempts} attempts. Never share it.",
        "otp.subject": "Your one-time code",
        "otp.body": "Your one-time code for \"{title}\" is below. It is valid for {minutes} minutes.",
        "reminder.subject": "Reminder: {title} is waiting for you",
        "completed.subject": "Completed: {title}",
        "completed.body": "Hello {name},\n\nAll parties have completed \"{title}\" ({envelope_id}).\n{attach_note}\nSigned PDF SHA-256: {hash}",
        "action.sign": "signature", "action.approve": "approval", "action.view": "review",
    },
    "hi": {
        "email.open": "दस्तावेज़ देखें",
        "email.footer": "यह {product} का स्वचालित संदेश है। इस ईमेल को साझा न करें।",
        "invite.subject": "{sender} ने आपके हस्ताक्षर का अनुरोध किया है: {title}",
        "invite.body": "नमस्ते {name},\n\n{sender} ने \"{title}\"{step} पर आपके {action} का अनुरोध किया है।\n{message}\nनीचे दिए गए सुरक्षित लिंक का उपयोग करें।{auth_note}\n\nयह लिंक {expires} को समाप्त होगा।",
        "invite.auth_note": " आपका एक्सेस कोड अलग से भेजा जाएगा।",
        "code.subject": "\"{title}\" के लिए आपका एक्सेस कोड",
        "code.body": "नमस्ते {name},\n\n\"{title}\" के लिए आपका एक्सेस कोड नीचे है। यह {hours} घंटे में समाप्त होगा और {attempts} प्रयासों की अनुमति देता है। इसे साझा न करें।",
        "otp.subject": "आपका वन-टाइम कोड",
        "otp.body": "\"{title}\" के लिए आपका वन-टाइम कोड नीचे है। यह {minutes} मिनट तक मान्य है।",
        "reminder.subject": "अनुस्मारक: {title} आपकी प्रतीक्षा कर रहा है",
        "completed.subject": "पूर्ण: {title}",
        "completed.body": "नमस्ते {name},\n\n\"{title}\" ({envelope_id}) सभी पक्षों द्वारा पूर्ण कर दिया गया है।\n{attach_note}\nहस्ताक्षरित PDF SHA-256: {hash}",
        "action.sign": "हस्ताक्षर", "action.approve": "अनुमोदन", "action.view": "समीक्षा",
    },
}
LANGS = tuple(MESSAGES)


def t(key: str, lang: str = "en", **kw) -> str:
    s = MESSAGES.get(lang, {}).get(key) or MESSAGES["en"].get(key, key)
    try:
        return s.format(**kw)
    except (KeyError, IndexError):
        return s
