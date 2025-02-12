import cv2
import mediapipe as mp
import pyautogui
import numpy as np
from math import hypot
from pynput.mouse import Button, Controller
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import screen_brightness_control as sbc
import time

class GestureController:
    def __init__(self):
        # Initialize screen dimensions and controls
        self.screen_width, self.screen_height = pyautogui.size()
        self.mouse = Controller()
        pyautogui.FAILSAFE = False
        
        # Initialize MediaPipe hands
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.75,
            max_num_hands=2
        )
        self.draw = mp.solutions.drawing_utils
        
        # Initialize audio control
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume = cast(interface, POINTER(IAudioEndpointVolume))
        self.volRange = self.volume.GetVolumeRange()
        self.minVol, self.maxVol = self.volRange[0], self.volRange[1]
        
        # State tracking
        self.mode = "mouse"  # "mouse" or "multimedia"
        self.cursor_paused = False
        self.last_screenshot_time = 0
        
    def get_finger_state(self, hand_landmarks):
        """Returns the state of each finger (up/down) as a list"""
        fingers = []
        
        # Thumb
        if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
            fingers.append(1)
        else:
            fingers.append(0)
            
        # Other fingers
        tips = [8, 12, 16, 20]  # landmark indices for finger tips
        for tip in tips:
            if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip-2].y:
                fingers.append(1)
            else:
                fingers.append(0)
                
        return fingers
    
    def get_distance(self, point1, point2):
        """Calculate distance between two points"""
        return hypot(point1.x - point2.x, point1.y - point2.y)
    
    def is_mode_switch_gesture(self, fingers):
        """Check for thumb and pinky up, others down"""
        return fingers == [1, 0, 0, 0, 1]
    
    def process_mouse_control(self, frame, hand_landmarks):
        """Process gestures for mouse control mode"""
        fingers = self.get_finger_state(hand_landmarks)
        
        # Get index finger tip position
        index_tip = hand_landmarks.landmark[8]
        
        # Mouse movement (index + middle up)
        if fingers[1] and fingers[2] and not fingers[0]:
            if not self.cursor_paused:
                x = int(index_tip.x * self.screen_width)
                y = int(index_tip.y * self.screen_height)
                pyautogui.moveTo(x, y)
                cv2.putText(frame, "Moving Cursor", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (255, 255, 255), 2)
        
        # Pause movement (index + middle + thumb up)
        if fingers[0] and fingers[1] and fingers[2] and not fingers[3] and not fingers[4]:
            self.cursor_paused = True
            cv2.putText(frame, "Movement Paused, close thumb to move cursor", 
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        else:
            self.cursor_paused = False
        
        # Right click (index + thumb up)
        if fingers[0] and fingers[1] and not fingers[2] and not fingers[3] and not fingers[4]:
            self.mouse.click(Button.right)
            cv2.putText(frame, "Right Click", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (255, 255, 255), 2)
            time.sleep(0.2)
        
        # Left click (middle + thumb up)
        if fingers[0] and not fingers[1] and fingers[2] and not fingers[3] and not fingers[4]:
            self.mouse.click(Button.left)
            cv2.putText(frame, "Left Click", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (255, 255, 255), 2)
            time.sleep(0.2)
        
        # Screenshot (closed fist)
        if not any(fingers):
            current_time = time.time()
            if current_time - self.last_screenshot_time > 1:  # Prevent multiple screenshots
                pyautogui.screenshot(f'screenshot_{int(current_time)}.png')
                cv2.putText(frame, "Screenshot taken", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (255, 255, 255), 2)
                self.last_screenshot_time = current_time
        
        # Scroll (middle + ring up)
        if not fingers[0] and not fingers[1] and fingers[2] and fingers[3] and not fingers[4]:
            y_move = hand_landmarks.landmark[12].y
            if y_move < 0.3:  # Scroll up
                pyautogui.scroll(50)
                cv2.putText(frame, "Scrolling Up", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (255, 255, 255), 2)
            elif y_move > 0.7:  # Scroll down
                pyautogui.scroll(-50)
                cv2.putText(frame, "Scrolling Down", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (255, 255, 255), 2)
    
    def process_multimedia_control(self, frame, hands_landmarks):
        """Process gestures for multimedia control mode"""
        for hand_landmarks, handedness in hands_landmarks:
            # Determine if it's left or right hand
            is_right = handedness.classification[0].label == "Right"
            
            # Process pinch gesture
            thumb_tip = hand_landmarks.landmark[4]
            index_tip = hand_landmarks.landmark[8]
            pinch_distance = self.get_distance(thumb_tip, index_tip)
            
            if is_right:  # Volume control with right hand
                vol = np.interp(pinch_distance, [0.02, 0.2], [self.minVol, self.maxVol])
                self.volume.SetMasterVolumeLevel(vol, None)
                
                # Draw volume bar
                volBar = np.interp(pinch_distance, [0.02, 0.2], [400, 150])
                volPer = np.interp(pinch_distance, [0.02, 0.2], [0, 100])
                cv2.rectangle(frame, (50, 150), (85, 400), (255, 0, 0), 3)
                cv2.rectangle(frame, (50, int(volBar)), (85, 400), (255, 0, 0), cv2.FILLED)
                cv2.putText(frame, f'Volume: {int(volPer)}%', (40, 450), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)
            
            else:  # Brightness control with left hand
                brightness = np.interp(pinch_distance, [0.02, 0.2], [0, 100])
                sbc.set_brightness(int(brightness))
                cv2.putText(frame, f'Brightness: {int(brightness)}%', (40, 500), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
    
    def run(self):
        cap = cv2.VideoCapture(0)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame = cv2.flip(frame, 1)
            frameRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frameRGB)
            
            # Display current mode
            cv2.putText(frame, f"Mode: {'Mouse Navigation' if self.mode == 'mouse' else 'Multimedia Control'}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            if results.multi_hand_landmarks:
                # Draw landmarks on all hands
                for hand_landmarks in results.multi_hand_landmarks:
                    self.draw.draw_landmarks(frame, hand_landmarks, self.mpHands.HAND_CONNECTIONS)
                
                # Check for mode switch gesture on primary hand
                primary_hand = results.multi_hand_landmarks[0]
                fingers = self.get_finger_state(primary_hand)
                if self.is_mode_switch_gesture(fingers):
                    self.mode = "multimedia" if self.mode == "mouse" else "mouse"
                    time.sleep(0.5)  # Prevent rapid mode switching
                
                # Process gestures based on current mode
                if self.mode == "mouse":
                    self.process_mouse_control(frame, primary_hand)
                else:
                    hands_with_handedness = zip(results.multi_hand_landmarks, results.multi_handedness)
                    self.process_multimedia_control(frame, hands_with_handedness)
            
            cv2.imshow('Gesture Control', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    controller = GestureController()
    controller.run()
