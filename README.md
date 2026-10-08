# 🎙️ CMK Voice Clone — Colab (အလကား)

Google Colab ရဲ့ **အလကား GPU** သုံးပြီး voice clone လုပ်တဲ့နည်း။
ပိုက်ဆံ ပေးစရာ မလိုဘူး။

---

## လိုအပ်တာ

- Google account (Gmail)
- ဒီ repo က `cmk-voice-clone-colab.ipynb` ဖိုင်

## အသုံးပြုနည်း

### 1. Notebook ဖွင့်

**နည်း A — Colab ကနေ တိုက်ရိုက်:**

1. [colab.research.google.com](https://colab.research.google.com) ဖွင့်
2. **File** → **Open notebook** → **GitHub** tab
3. `danielmin-hub/cmk-voice-clone` ရိုက် → `cmk-voice-clone-colab.ipynb` ရွေး

**နည်း B — ဖိုင် download လုပ်ပြီး:**

1. ဒီ repo က `cmk-voice-clone-colab.ipynb` ကို download
2. Colab မှာ **File** → **Upload notebook**

### 2. GPU ပြောင်း

**Runtime** → **Change runtime type** → **Hardware accelerator: T4 GPU** → **Save**

### 3. Cell တွေ Run

အပေါ်ကနေ အောက်ကို အစဉ်လိုက် ▶️ နှိပ်:

| Cell | ဘာလုပ်လဲ | ကြာချိန် |
| --- | --- | --- |
| 1 | Packages သွင်း | ၁-၂ မိနစ် |
| 2 | Drive ချိတ် (Allow နှိပ်) | စက္ကန့်ပိုင်း |
| 3 | Model download + load | ၅-၁၀ မိနစ် (ပထမဆုံး) |
| 4 | Core engine | စက္ကန့်ပိုင်း |
| 5 | Web UI စတင် | စက္ကန့်ပိုင်း |

### 4. အသံထုတ်

Cell 5 run ပြီးရင် **Gradio link** ပေါ်လာမယ် → နှိပ်:

**🎤 Clone Voice tab:**

1. 📝 စာသား ထည့် (ပြောခိုင်းချင်တဲ့ စာ)
2. 🎵 ကိုယ့်အသံဖိုင် တင် (WAV အကောင်းဆုံး, ၁၀-၃၀ စက္ကန့်)
3. 📄 Reference Text ထည့် (အသံဖိုင်ထဲ ပြောထားတဲ့ စကား အတိအကျ)
4. **🎤 Clone ပြီး ထုတ်မယ်** နှိပ်

**🎭 Preset Voice tab:**

- ကြိုတင်သတ်မှတ်ထားတဲ့ voice တွေနဲ့ ထုတ် (VOICE\_DATABASE မှာ ထည့်ထားရင်)

**✨ Prompt Voice tab:**

- Style ရေးပြီး အသံထုတ် (ဥပမာ: "young male, calm and clear")

### 5. Output ယူ

- ထုတ်ပြီးသား အသံက **Drive** ထဲမှာ auto-save: `MyDrive/CMK_VoiceClone/outputs/`
- Gradio UI ကနေလဲ download လို့ရတယ်

---

## အကြံပြုချက်များ

- 🎤 **အသံသွင်းတာ:** တိတ်ဆိတ်တဲ့ အခန်း, ၁၀-၃၀ စက္ကန့်, သဘာဝကျကျ ပြော
- 📄 **Reference Text:** အသံဖိုင်ထဲ ပြောထားတာနဲ့ **စကားလုံး အတိအကျ** တူရမယ်
- ⏱️ **အချိန်:** စာရှည်ရင် အပိုင်းလိုက် ခွဲထုတ်, ပြီးမှ ဆက်
- 💾 **Drive:** Output တွေ Drive မှာ ရှိတယ်, Colab ပိတ်လဲ မပျောက်ဘူး

## ကန့်သတ်ချက်များ

- Colab **free GPU** က အချိန်ကန့်သတ် ရှိတယ် (များသောအားဖြင့် နာရီအနည်းငယ်/နေ့)
- GPU သုံးနေတုန်း browser tab ကို **ဖွင့်ထားရ**မယ်
- Session ပြတ်ရင် model ပြန် load ရမယ် (၅-၁၀ မိနစ်)
- တစ်ခါ တစ်ယောက်တည်း သုံးလို့ရတယ်

## ပိုက်ဆံ ပေးချင်ရင်

Colab Pro ($10/လ) ဆို GPU အချိန် ပိုရတယ်။ သို့မဟုတ် ဒီ repo ထဲက
RunPod server ဖိုင်တွေ (`server.py`, `Dockerfile`) သုံးပြီး ကိုယ့် GPU server
run လို့ရတယ် — အသေးစိတ် `README-MM.md` မှာ ကြည့်။