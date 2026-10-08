# CMK Voice Clone API

ကိုယ်ပိုင် voice clone service။ အသံတို တစ်ခု upload လုပ်ထားရုံနဲ့
စာမှန်သမျှ — မြန်မာလို အပါအဝင် — ကို အဲဒီအသံနဲ့ ပြောခိုင်းလို့ရတယ်။

VoxCPM (openbmb) ကို အခြေခံထားတဲ့ ကိုယ်ပိုင် implementation။

---

## အလုပ်လုပ်ပုံ

1. **အသံသွင်း** — ၁၀–၃၀ စက္ကန့်၊ ရှင်းရှင်းလင်းလင်း ပြောထားတာ (ဖုန်းနဲ့ သွင်းလဲ ရတယ်)။
2. **Upload လုပ်** — သွင်းထားတဲ့ စကားရဲ့ စာသား အတိအကျ နဲ့ တွဲတင်ပေး။
   စာသား မှန်မှ model က အသံကို မိမိရရ ဖမ်းနိုင်မယ်။
3. **စာထည့် ပြောခိုင်း** — `/tts` ကို `voice_id` နဲ့ စာပို့၊ WAV ပြန်ရမယ်။

Model (VoxCPM) က ပထမဆုံး run တဲ့အခါ Hugging Face ကနေ သူ့ဘာသာ download
လုပ်တယ်။ ကိုယ်တိုင် ဘာမှ ဆွဲစရာ မလိုဘူး။

## API အတိုချုပ်

| Method | Path             | ဘာလုပ်လဲ                                              |
|--------|------------------|--------------------------------------------------------|
| GET    | `/health`        | Model load ပြီးပြီလား? ဘယ် device? voice ဘယ်နှခု?      |
| GET    | `/voices`        | ဒီ server မှာ သိမ်းထားတဲ့ voice တွေ                   |
| POST   | `/upload-voice`  | Form: `audio` file, `name`, `prompt_text` → `voice_id` |
| POST   | `/tts`           | JSON: `text`, `voice_id` (+ `guide`, `steps` ရွေးနိုင်) |
| POST   | `/clone`         | တစ်ခါသုံး: `audio` + `text` → WAV, ဘာမှ မသိမ်းဘူး       |
| POST   | `/style-voice`   | JSON: `text`, `style` ("warm narrator") — sample မလို  |

အသံအဝင်/အထွက် အားလုံး 16 kHz mono WAV။ Response က WAV bytes အတိုင်း။

Voice register လုပ်တဲ့ နမူနာ (curl):

```bash
curl -X POST http://POD_IP:8000/upload-voice \
  -F "audio=@my-voice.wav" \
  -F "name=ကျွန်တော့်အသံ" \
  -F "prompt_text=သွင်းထားတဲ့ စကား အတိအကျ"
# -> {"voice_id": "a1b2c3d4e5f6", "label": "ကျွန်တော့်အသံ"}
```

စာထည့် ပြောခိုင်းတဲ့ နမူနာ:

```bash
curl -X POST http://POD_IP:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "မင်္ဂလာပါ", "voice_id": "a1b2c3d4e5f6"}' \
  --output out.wav
```

## RunPod မှာ တင်နည်း

1. **Account + ပိုက်ဆံ** — runpod.io မှာ sign up လုပ်၊ $10 လောက် credit ထည့် စမ်းကြည့်။
2. **Code ကို pod ပေါ် တင်။** အလွယ်ဆုံး: ဒီ ၄ ဖိုင်ကို GitHub repo မှာ တင်၊
   RunPod မှာ *Pods → Deploy → Build from GitHub* ရွေး၊ repo ကို ညွှန်။
3. **GPU ရွေး။** A40 (~$0.49/hr) က မူရင်း 0.5B model အတွက် လုံလောက်တယ်။
   VoxCPM 1.5/2 အကြီးတွေ သုံးချင်ရင် VRAM 16 GB+ လိုတယ်။
4. **Port 8000** (TCP) ဖွင့် — API ကို လှမ်းခေါ်လို့ရအောင်။
5. **Network volume ကို `/workspace` မှာ attach လုပ်။** ဒါမလုပ်ရင်
   pod restart တိုင်း upload လုပ်ထားတဲ့ voice တွေ ပျောက်မယ်။
6. **Deploy နှိပ် စောင့်။** ပထမဆုံး boot မှာ model (~1.5 GB) download လုပ်
   တယ် — ၅–၁၀ မိနစ် ပေးထား၊ ပြီးရင် `http://POD_IP:8000/health` ဖွင့်။
   `"status": "ok"` ပြရင် အဆင်သင့်ဖြစ်ပြီ။

### Model ပြောင်းချင်ရင်

Pod env var `CMK_VOX_MODEL` သတ်မှတ်:

- `openbmb/VoxCPM-0.5B` — မူရင်း၊ ~1.5 GB၊ VRAM 8 GB နဲ့ ရတယ်
- `openbmb/VoxCPM1.5` — ~1.9 GB၊ အရည်အသွေး ပိုကောင်း
- `openbmb/VoxCPM2` — ~4.6 GB၊ အကောင်းဆုံး၊ VRAM 16 GB+ လိုတယ်

ကျန်တဲ့ setting တွေ: `CMK_GEN_TIMEOUT` (စက္ကန့်၊ မူရင်း 900),
denoiser ဖွင့်ချင်ရင် `CMK_USE_DENOISER=1`, `PORT`။

## အသံလှလှ ရအောင် အကြံပြုချက်

- တိတ်ဆိတ်တဲ့ အခန်းမှာ သွင်း၊ ၁၀–၃၀ စက္ကန့်၊ သဘာဝကျကျ ပြော။
- `prompt_text` က သွင်းထားတဲ့ အသံနဲ့ **စကားလုံး အတိအကျ** တူရမယ်။
- မြန်မာစာ ရတယ် — `။` ကို စာကြောင်းဆုံး အဖြစ် နားလည်တယ်။
- အထွက် မြန်နေသလို ခံစားရရင် `guide` လျှော့ (1.6 စမ်း); အသံကို
  မလိုက်ဘူးဆို `guide` မြှင့် (2.6 စမ်း)။

## သိထားရမယ့် ကန့်သတ်ချက်တွေ

- Pod တစ်ခု တစ်ခါ တစ်ခု ပဲ ထုတ်ပေးနိုင်တယ် (GPU အလုပ် တန်းစီရတယ်)။
  လူများများ သုံးမယ်ဆို pod နှစ်ခု run။
- Streaming မရဘူး — request တစ်ခုချင်းစီ WAV အပြည့်ပြန်ပေးတယ်။
- မြန်မာ အထွက် အရည်အသွေး ကို အသံအစစ်နဲ့ စမ်းကြည့်ပြီးမှ
  တကယ် သုံးဖို့ ဆုံးဖြတ်။
