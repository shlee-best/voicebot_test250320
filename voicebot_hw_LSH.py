import streamlit as st
import openai
import os
from dotenv import load_dotenv
from audiorecorder import audiorecorder
from datetime import datetime
import base64
import json
import requests

load_dotenv()

client = openai.OpenAI()

def get_weather(location):
    response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current_weather=true")
    if response.status_code == 200:
        data = response.json()
        return f"현재 {location}의 온도는 {data['current_weather']['temperature']}°C 입니다."
    return "날씨 정보를 가져오는데 실패했습니다."

def get_exchange_rate():
    response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
    if response.status_code == 200:
        data = response.json()
        rate = data['rates'].get('KRW', '알 수 없음')
        return f"현재 원-달러 환율은 1달러당 {rate}원 입니다."
    return "환율 정보를 가져오는데 실패했습니다."

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "특정 장소의 날씨를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"],
            "additionalProperties": False
        },
        "strict": True
    }
}, {
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": "현재 원-달러 환율을 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "strict": True
    }
}]

def generate_chat_response(messages):
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        messages.append({
            "role": "assistant",
            "tool_calls": tool_calls
        })

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            if func_name == "get_weather":
                result =  get_weather(func_args["location"])
            elif func_name == "get_exchange_rate":
                result = get_exchange_rate()
            else:
                result = "기능을 찾을 수 없습니다."
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,   
                "content": str(result)
            })

        final_response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=messages,
            tools=tools
        )

        return final_response.choices[0].message.content

    else:
        return response.choices[0].message.content

def speech_to_text(speech):
    filename='input.mp3'
    speech.export(filename, format="mp3")

    with open(filename, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )

    os.remove(filename)
    
    return transcription.text

def text_to_speech(text):
    filename = "output.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    
    with open(filename, "wb") as f:
        f.write(response.content)

    # 음원 파일 자동 재생
    with open(filename, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay="True">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

    # 파일 삭제
    os.remove(filename)

# 메인 함수 정의
def main():
    # 페이지 설정: 제목과 레이아웃 설정
    st.set_page_config(
        page_title="🎤 보이스 챗봇",  # 페이지 제목
        layout="wide"  # 페이지 레이아웃을 넓게 설정
    )

    # 페이지 헤더 추가
    st.header("🎤 보이스 챗봇")

    # 구분선 추가
    st.markdown("---")

    # 확장 가능한 섹션 생성 (기본적으로 열려 있음)
    with st.expander("🎤 보이스 챗봇사용", expanded=True):
        # 보이스 챗봇 프로그램에 대한 설명 추가
        st.write(
        """     
        -🌦️ **날씨**: Open-Meteo API에서 최신 날씨 정보를 가져옵니다.
  💰    - **환율**: USD-KRW 환율 정보를 제공합니다.
        - 🗣️ **음성 지원**: STT(Speech-To-Text) 및 TTS(Text-To-Speech)를 지원합니다.
        - 💡 **다국어 지원**: 한글과 영어로 대화가 가능합니다.
        """
        )

        # 추가적인 여백을 위한 빈 마크다운
        st.markdown("")

    system_message = "당싱은 친절한 헬퍼입니다. 30 단어 미만의 한국어로 답변해 주세요."

    # session state 초기화
    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "system", "content": system_message}]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("보이스 전송. 마이크를 클릭하고 말씀하세요.")

        audio = audiorecorder()
        if (audio.duration_seconds > 0):
            st.audio(audio.export().read())

            question = speech_to_text(audio)

            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"] + [("user", now, question)]

            st.session_state["messages"] = st.session_state["messages"] + [{"role": "user", "content": question}]


    with col2:
        st.subheader("대화 내역")

        if  audio.duration_seconds > 0:
            response_content = generate_chat_response(st.session_state["messages"])

            st.session_state["messages"] = st.session_state["messages"] + [{"role": "assistant", "content": response_content}]

            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"] + [("bot", now, response_content)]

            for sender, time, message in st.session_state["chat"]:
                if sender == "user":
                    st.write(f'<div style="display:flex;align-items:center;"><div style="background-color:#007AFF;color:white;border-radius:12px;padding:8px 12px;margin-right:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', 
                             unsafe_allow_html=True)
                    st.write("")
                else:
                    st.write(f'<div style="display:flex;align-items:center;justify-content:flex-end;"><div style="background-color:lightgray;border-radius:12px;padding:8px 12px;margin-left:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', 
                             unsafe_allow_html=True)
                    st.write("")

            text_to_speech(response_content)

# 스크립트가 직접 실행될 때 메인 함수 호출
if __name__=="__main__":
    main()