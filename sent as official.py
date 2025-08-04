import cv2
import mediapipe as mp
import time, datetime, json, os

class SonaraLite:
    def __init__(self):
        self.data_file = os.path.join(os.path.dirname(__file__), 'patient_data.json')
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.hands = mp.solutions.hands.Hands(max_num_hands=2)
        self.draw = mp.solutions.drawing_utils
        self.tipIds = [4, 8, 12, 16, 20]
        self.reset_session()
        self.data = self.load_data()
        self.hand_detected_once = False

    def reset_session(self):
        self.count, self.prev_fingers = 0, None
        self.last_time, self.start_time = time.time(), time.time()
        self.paused, self.pause_time, self.total_paused = False, 0, 0
        self.exercise_log, self.target = [], 20
        self.stored_fingers = -1
        self.session_complete = False
        self.hand_detected_once = False

    def load_data(self):
        if os.path.exists(self.data_file):
            return json.load(open(self.data_file))
        return {
            'total_exercises': 0,
            'total_sessions': 0,
            'daily_streak': 0,
            'last_session_date': None,
            'session_history': []
        }

    def save_data(self):
        json.dump(self.data, open(self.data_file, 'w'), indent=2)

    def toggle_pause(self):
        if self.session_complete:
            print("Session already completed. Cannot pause.")
            return
        if self.paused:
            self.total_paused += time.time() - self.pause_time
            print("Session RESUMED")
        else:
            self.pause_time = time.time()
            print("Session PAUSED")
        self.paused = not self.paused

    def get_time(self):
        if not self.hand_detected_once:
            return 0
        if self.session_complete:
            return self.end_time - self.start_time - self.total_paused
        now = time.time()
        return (self.pause_time if self.paused else now) - self.start_time - self.total_paused

    def get_speed(self):
        mins = self.get_time() / 60
        return round(self.count / mins, 1) if mins > 0 else 0

    def feedback(self):
        if self.session_complete:
            return "Today's Exercise Completed!", (0, 255, 0)
        p = (self.count * 100) / self.target
        streak = f" {self.data['daily_streak']} Day Streak!" if self.data['daily_streak'] > 1 else ""
        if p >= 75:
            return "Great Progress! Almost There!" + streak, (0, 255, 0)
        elif p >= 50:
            return "Halfway There! Keep It Up!" + streak, (0, 255, 255)
        elif p >= 25:
            return "Good Start! You're Doing Great!" + streak, (255, 255, 0)
        return "Let's Begin Your Therapy!" + streak, (255, 255, 255)

    def exercise_name(self, fingers):
        if fingers < 0:
            return "", ""
        names = [
            (0, "Closed Fist Exercise", "Basic"),
            (1, "Index Pointing Exercise", "Basic"),
            (2, "Peace Sign Exercise", "Intermediate"),
            (3, "Three-Finger Stretch", "Intermediate"),
            (4, "Four-Finger Extension", "Advanced"),
            (5, "Open Palm Exercise", "Advanced")
        ]
        for n, name, level in names:
            if fingers == n:
                return level, name
        return "Custom", f"Pattern-{fingers} Exercise"

    def update_log(self, fingers):
        level, name = self.exercise_name(fingers)
        log = {
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'finger_count': fingers,
            'exercise_name': name,
            'difficulty': level,
            'session_exercise_number': self.count,
            'exercises_per_minute': self.get_speed()
        }
        self.exercise_log.append(log)

    def update_stats(self):
        today = datetime.date.today().strftime('%Y-%m-%d')
        if self.data['last_session_date'] != today:
            yest = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            self.data['daily_streak'] = self.data['daily_streak'] + 1 if self.data['last_session_date'] == yest else 1
            self.data['last_session_date'] = today
        session = {
            'date': today,
            'exercises_completed': self.count,
            'session_duration': int(self.get_time()),
            'target_achieved': self.count >= self.target,
            'exercise_log': self.exercise_log
        }
        self.data['session_history'].append(session)
        self.data['total_exercises'] += self.count
        self.data['total_sessions'] += 1
        self.data['session_history'] = self.data['session_history'][-30:]
        self.save_data()  # Save instantly

    def count_fingers(self, lm, label):
        fingers = [0] * 5
        fingers[0] = int(lm[self.tipIds[0]][1] < lm[self.tipIds[0]-1][1]) if label == 'Right' else int(lm[self.tipIds[0]][1] > lm[self.tipIds[0]-1][1])
        for i in range(1, 5):
            fingers[i] = int(lm[self.tipIds[i]][2] < lm[self.tipIds[i]-2][2])
        return sum(fingers)

    def draw_ui(self, img, fingers):
        h, w = img.shape[:2]
        p = min(100, int((self.count * 100) / self.target))
        msg, color = self.feedback()
        level, name = self.exercise_name(fingers)

        if p >= 100:
            progress_color = (0, 255, 0)
        elif p >= 50:
            progress_color = (0, 255, 255)
        else:
            progress_color = (0, 0, 255)

        cv2.rectangle(img, (0, 0), (w, 60), (0, 100, 50) if not self.paused else (100, 100, 0), -1)
        cv2.putText(img, "THERAPY MODE" + (" - PAUSED" if self.paused else ""), (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 2)
        cv2.putText(img, f'Fingers Detected: {fingers if fingers >= 0 else "-"}', (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
        cv2.putText(img, f'Exercises: {self.count}/{self.target}', (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,255), 2)

        if fingers >= 0:
            cv2.putText(img, f'{name} ({level})', (20, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

        cv2.putText(img, msg, (20, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        cv2.rectangle(img, (20, 250), (420, 280), (100,100,100), -1)
        cv2.rectangle(img, (20, 250), (20 + 4*p, 280), progress_color, -1)

        mins, secs = divmod(int(self.get_time()), 60)
        if not self.session_complete:
            cv2.putText(img, f'Session Time: {mins}m {secs}s', (20, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
            spd = self.get_speed()
            if spd > 0:
                cv2.putText(img, f'Speed: {spd} exercises/min', (20, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
        if self.data['daily_streak'] > 0:
            cv2.putText(img, f'{self.data["daily_streak"]} Day Streak!', (20, 380), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,165,255), 2)

        cv2.rectangle(img, (0, h-40), (w, h), (0, 50, 0), -1)
        cv2.putText(img, 'Q = Quit | R = Reset | S = Stats', (20, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

    def show_stats(self):
        print("\n" + "="*50)
        print("PATIENT STATISTICS")
        print("="*50)
        print("Total Sessions:", self.data['total_sessions'])
        print("Total Exercises:", self.data['total_exercises'])
        print("Daily Streak:", self.data['daily_streak'])
        print("Current Session:", self.count, "/", self.target)
        print("\nRecent Sessions:")
        for s in self.data['session_history'][-5:]:
            print(f"  {s['date']}: {s['exercises_completed']} exercises - {'Completed' if s['target_achieved'] else 'In Progress'}")

    def run(self):
        while True:
            ret, img = self.cap.read()
            if not ret:
                break
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = self.hands.process(imgRGB)
            fingers = -1
            if res.multi_hand_landmarks:
                fingers = 0
                if not self.hand_detected_once:
                    self.hand_detected_once = True
                    self.start_time = time.time()
                for lm, info in zip(res.multi_hand_landmarks, res.multi_handedness):
                    lmlist = [(id, int(p.x*img.shape[1]), int(p.y*img.shape[0])) for id, p in enumerate(lm.landmark)]
                    fingers += self.count_fingers(lmlist, info.classification[0].label)
                    self.draw.draw_landmarks(img, lm, mp.solutions.hands.HAND_CONNECTIONS)
            now = time.time()
            if not self.paused and not self.session_complete and self.hand_detected_once:
                if self.prev_fingers is not None and fingers != self.prev_fingers and now - self.last_time > 1:
                    self.count += 1
                    self.update_log(fingers)
                    self.last_time = now
                    if self.count >= self.target:
                        self.session_complete = True
                        self.end_time = time.time()
                        print("Session Completed. Exercise Target Reached.")
                        self.update_stats()  # Save immediately
                elif self.prev_fingers is None:
                    self.prev_fingers = fingers
                    self.last_time = now
            self.prev_fingers = fingers
            self.draw_ui(img, fingers if not self.paused else self.stored_fingers)
            if self.paused:
                self.stored_fingers = fingers
            cv2.imshow("Sonara Lite", img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key in [ord('p'), ord('P')]:
                self.toggle_pause()
            elif key in [ord('r'), ord('R')]:
                self.reset_session()
                print("Session reset!")
            elif key in [ord('s'), ord('S')]:
                self.show_stats()
        self.cleanup()

    def cleanup(self):
        if self.count > 0 and not self.session_complete:
            self.update_stats()
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    SonaraLite().run()
