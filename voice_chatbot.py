import json
import requests
import speech_recognition as sr
from gtts import gTTS
import pygame
import tempfile
import os

class VoiceChatbot:
    def __init__(self):
        self.api_key = "AIzaSyAeYodfvGxHtqUp7nSV6o4Xk-ZeNPJmGYU"
        self.memory = []
        self.indexes = self.load_json_files()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
        # Adjust for ambient noise
        print("Adjusting for ambient noise... Please wait.")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
        print("Ready!")

    def load_abbreviations(self):
        try:
            with open("abbreviations.json", 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def expand_query_with_abbreviations(self, query):
        abbreviations = self.load_abbreviations()
        query_lower = query.lower().strip()
        
        for category in abbreviations.values():
            if isinstance(category, dict):
                for abbrev, full_term in category.items():
                    if query_lower == abbrev or query_lower in abbrev.split():
                        return full_term
        return query_lower

    def load_json_files(self):
        files_to_load = [
            ("policy_chunks.json", "policy"),
            ("functionaries.json", "people"),
            ("important_contacts.json", "contacts"),
            ("Admission.json", "admission"),
            ("dataset.json", "general")
        ]
        
        indexes = {}
        
        for filename, data_type in files_to_load:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    indexes[filename.replace('.json', '')] = {
                        "data": data, 
                        "type": data_type
                    }
                    print(f"✓ Loaded {filename}")
            except FileNotFoundError:
                print(f"✗ Warning: {filename} not found")
            except json.JSONDecodeError:
                print(f"✗ Error: Invalid JSON in {filename}")
        
        return indexes

    def search_all_chunks(self, query):
        query_lower = query.lower()
        matched_chunks = []
        
        expanded_query = self.expand_query_with_abbreviations(query)
        abbreviations = self.load_abbreviations()
        
        search_terms = [query_lower, expanded_query]
        
        for category in abbreviations.values():
            if isinstance(category, dict):
                for abbrev, full_term in category.items():
                    if query_lower in abbrev or abbrev in query_lower:
                        search_terms.append(full_term)
                    if query_lower in full_term or full_term in query_lower:
                        search_terms.append(abbrev)
        
        search_terms = list(set(search_terms))

        for index_name, index_data in self.indexes.items():
            data_type = index_data["type"]
            data = index_data["data"]
            
            if data_type == "people":
                if isinstance(data, list):
                    for person in data:
                        name = person.get("name", "").lower()
                        position = person.get("position", "").lower()

                        match_found = False
                        for term in search_terms:
                            if (term in name or term in position or
                                any(word in name for word in term.split()) or
                                any(word in position for word in term.split())):
                                match_found = True
                                break
                        
                        if match_found:
                            matched_chunks.append({
                                "content": f"Name: {person.get('name', '')}\nPosition: {person.get('position', '')}",
                                "source": index_name,
                                "type": "person",
                                "score": 5
                            })

            elif data_type == "admission":
                if isinstance(data, dict) and "Programs" in data:
                    for program in data["Programs"]:
                        program_text = json.dumps(program).lower()
                        
                        score = 0
                        for term in search_terms:
                            if term in program_text:
                                score += 1
                        
                        if score > 0:
                            content_parts = []
                            if "CourseName" in program:
                                content_parts.append(f"Course: {program['CourseName']}")
                            if "Duration" in program:
                                content_parts.append(f"Duration: {program['Duration']}")
                            if "AnnualFee" in program:
                                content_parts.append(f"Fee: {program['AnnualFee']}")
                            
                            matched_chunks.append({
                                "content": "\n".join(content_parts),
                                "source": index_name,
                                "type": "admission",
                                "score": score
                            })

        matched_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        return matched_chunks

    def generate_answer_from_gemini(self, query, context_chunks):
        if not context_chunks:
            return "Sorry, I couldn't find any relevant information."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        context_text = ""
        for chunk in context_chunks[:3]:
            context_text += chunk["content"] + "\n\n"

        prompt = f"""Answer this question using the provided information:

{context_text}

Question: {query}

Answer briefly and clearly:"""

        data = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10 )
            if response.status_code == 200:
                result = response.json()
                return result["candidates"][0]["content"]["parts"][0]["text"]
            return "Sorry, the information service is currently unavailable."
        except Exception as e:
            return f"Error: {str(e)}"

    def speak_text(self, text):
        try:
            tts = gTTS(text=text, lang='en')
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tts.save(tmp_file.name)
                
                pygame.mixer.music.load(tmp_file.name)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                
                os.unlink(tmp_file.name)
                
        except Exception as e:
            print(f"Error with text-to-speech: {str(e)}")

    def listen_for_speech(self):
        try:
            print("🎤 Listening... (speak now)")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
            
            print("🔄 Processing speech...")
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text
            
        except sr.WaitTimeoutError:
            print("⏰ No speech detected")
            return None
        except sr.UnknownValueError:
            print("❌ Could not understand the audio")
            return None
        except sr.RequestError as e:
            print(f"❌ Error with speech recognition: {e}")
            return None

    def run(self):
        print("=" * 60)
        print("🎓 MANAV RACHNA UNIVERSITY CHATBOT")
        print("=" * 60)
        print("Commands:")
        print("• Type your question")
        print("• Say 'voice' to use voice input")
        print("• Say 'quit' to exit")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() == 'quit':
                    print("👋 Goodbye!")
                    break
                
                if user_input.lower() == 'voice':
                    speech_text = self.listen_for_speech()
                    if speech_text:
                        user_input = speech_text
                    else:
                        continue
                
                if not user_input:
                    continue
                
                print("🤖 Assistant: Thinking...")
                
                context_chunks = self.search_all_chunks(user_input)
                response = self.generate_answer_from_gemini(user_input, context_chunks)
                
                print(f"🤖 Assistant: {response}")
                
                print("🔊 Speaking response...")
                self.speak_text(response)
                
                self.memory.append((user_input, response))
                if len(self.memory) > 10:
                    self.memory = self.memory[-10:]
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    try:
        chatbot = VoiceChatbot()
        chatbot.run()
    except Exception as e:
        print(f"Failed to start chatbot: {str(e)}")
