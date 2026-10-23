// Minimal i18n scaffolding (FR-176..179). Add languages by extending DICT; missing keys fall back to English.
const DICT = {
  en: {
    start: 'Start', next: 'Next field', review: 'Review', finish: 'Sign & finish', decline: 'Decline', later: 'Finish later', consent: 'I agree to use electronic records and signatures',
    enterCode: 'Enter the access code that was sent to you separately.', unlock: 'Unlock document', sendCode: 'Email me a code', sendSms: 'Text me a code',
    reason: 'Reason for signing *', yourSig: 'Your signature', typed: 'Type', drawn: 'Draw', uploaded: 'Upload', clear: 'Clear', done: 'Done', fieldsLeft: '{n} required field(s) left',
    thanksNext: 'Thank you — your signature has been recorded. The next recipient has now been notified.', thanksDone: 'Thank you — you were the final signer. The completed document and certificate will be emailed to all parties.',
    declined: 'You declined this document. The sender has been informed.', saved: 'Progress saved. Use the same link to continue later.', language: 'Language',
  },
  hi: {
    start: 'शुरू करें', next: 'अगला फ़ील्ड', review: 'समीक्षा', finish: 'हस्ताक्षर करें और समाप्त करें', decline: 'अस्वीकार करें', later: 'बाद में पूरा करें', consent: 'मैं इलेक्ट्रॉनिक रिकॉर्ड और हस्ताक्षर के उपयोग से सहमत हूँ',
    enterCode: 'आपको अलग से भेजा गया एक्सेस कोड दर्ज करें।', unlock: 'दस्तावेज़ खोलें', sendCode: 'मुझे कोड ईमेल करें', sendSms: 'मुझे कोड SMS करें',
    reason: 'हस्ताक्षर का कारण *', yourSig: 'आपका हस्ताक्षर', typed: 'टाइप', drawn: 'बनाएँ', uploaded: 'अपलोड', clear: 'मिटाएँ', done: 'हो गया', fieldsLeft: '{n} आवश्यक फ़ील्ड शेष',
    thanksNext: 'धन्यवाद — आपका हस्ताक्षर दर्ज हो गया है। अगले प्राप्तकर्ता को सूचित कर दिया गया है।', thanksDone: 'धन्यवाद — आप अंतिम हस्ताक्षरकर्ता थे। पूर्ण दस्तावेज़ और प्रमाणपत्र सभी पक्षों को ईमेल किया जाएगा।',
    declined: 'आपने यह दस्तावेज़ अस्वीकार कर दिया। प्रेषक को सूचित कर दिया गया है।', saved: 'प्रगति सहेजी गई। बाद में उसी लिंक से जारी रखें।', language: 'भाषा',
  },
}
let lang = localStorage.getItem('vs_lang') || 'en'
export const LANGS = [['en', 'English'], ['hi', 'हिन्दी']]
export const setLang = (l) => { if (l && DICT[l]) { lang = l; localStorage.setItem('vs_lang', l) } }
export const getLang = () => lang
export const t = (k, vars = {}) => (DICT[lang]?.[k] ?? DICT.en[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '')
