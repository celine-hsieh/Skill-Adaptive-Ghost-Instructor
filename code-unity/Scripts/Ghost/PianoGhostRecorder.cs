using System.Collections.Generic;
using UnityEngine;
using System.IO;
using UnityEngine.InputSystem;
using TMPro;
using UnityEngine.UI;
using UnityEngine.InputSystem.EnhancedTouch;

[System.Serializable]
public class PianoKeyEvent
{
    public string keyName;
    public float pressTime;
    public float duration;
    public int finger;
}

[System.Serializable]
public class PianoGhostRecording
{
    public List<PianoKeyEvent> keyEvents = new List<PianoKeyEvent>();
}

public class PianoGhostRecorder : MonoBehaviour
{
    public bool isRecording = false;

     [HideInInspector] public bool isMeasuring = false;
    [HideInInspector] public int userNumber;
    
    private float recordingStartTime;
    private PianoGhostRecording currentRecording = new PianoGhostRecording();
    private Dictionary<string, (float, int)> keyDownTimes = new Dictionary<string, (float, int)>();
    
    public InputAction startStopAction;
    public TextMeshPro RecordText;

    void Update()
    {
        // Support both legacy Input and the new Input System for Space key
        bool spacePressed = (Keyboard.current != null && Keyboard.current.spaceKey.wasPressedThisFrame)
                            || Input.GetKeyDown(KeyCode.Space);

        if (spacePressed)
        {
            if (!isRecording) StartRecording();
            else StopAndSaveRecording();
        }
    }

    void OnEnable()
    {
        startStopAction.Enable();
        startStopAction.performed += ctx => ToggleRecording();
    }

    void OnDisable()
    {
        startStopAction.Disable();
    }

    void ToggleRecording()
    {
        if (!isRecording) StartRecording();
        else StopAndSaveRecording();
    }

    public void StartRecording()
    {
        currentRecording = new PianoGhostRecording();
        recordingStartTime = Time.time;
        isRecording = true;
        Debug.Log("Start Recording Piano Ghost！");
    }

    public void StartUserRecording()
    {
        currentRecording = new PianoGhostRecording();
        recordingStartTime = Time.time;
        Debug.Log("Start Recording Piano Ghost！");
    }
    public void WhenPress()
    {
        if (!isRecording)
        {
            StartRecording();
            RecordText.text = "Stop Recording";
        }
        else
        {
            StopAndSaveRecording();
            RecordText.text = "Start Recording";
        }
    }

    public void RecordKeyDown(string keyName, int finger)
    {
        if (isRecording || isMeasuring)
        {
            if (!keyDownTimes.ContainsKey(keyName))
            {
                float pressTime = Time.time - recordingStartTime;
                keyDownTimes[keyName] = (pressTime, finger);
            }
        }else return;

    }

    public void RecordKeyUp(string keyName)
    {
        if (isRecording || isMeasuring)
        {
            if (keyDownTimes.ContainsKey(keyName))
            {
                (float pressTime, int finger) = keyDownTimes[keyName];
                float releaseTime = Time.time - recordingStartTime;
                float duration = releaseTime - pressTime;

                currentRecording.keyEvents.Add(new PianoKeyEvent
                {
                    keyName = keyName,
                    pressTime = pressTime,
                    duration = duration,
                    finger = finger
                });

                keyDownTimes.Remove(keyName);

                Debug.Log($"Record Key Press: {keyName} at {pressTime} during {duration:F2}s");
            }
        }
        else return;
    }


    public void StopAndSaveRecording()
    {
        isRecording = false;
        Debug.Log($"Stop Record，total {currentRecording.keyEvents.Count} ");

        SaveRecordingToJson();
    }

    public void StopAndSaveUserPlay()
    {
        SaveUserRecordingToJson();

    }
    private void SaveRecordingToJson()
    {
        string json = JsonUtility.ToJson(currentRecording, true);
        string folderPath = Path.Combine(Application.dataPath, "PianoKeyEvents");
        if (!Directory.Exists(folderPath))
        {
            Directory.CreateDirectory(folderPath);
        }
        string baseFileName = $"recording";
        int version = 1;
        string filePath;

        do
        {
            filePath = Path.Combine(folderPath, $"{baseFileName}_v{version}.json");
            version++;
        } while (File.Exists(filePath));

        File.WriteAllText(filePath, json);

        Debug.Log($"Save Recording：{filePath}");
    }

    private void SaveUserRecordingToJson()
    {
        string json = JsonUtility.ToJson(currentRecording, true);
        string folderPath = Path.Combine(Application.dataPath, "PianoKeyEvents", "User");

        if (!Directory.Exists(folderPath))
            Directory.CreateDirectory(folderPath);

        string baseFileName = $"User{userNumber}";
        int version = 1;
        string filePath;

        do
        {
            filePath = Path.Combine(folderPath, $"{baseFileName}_v{version}.json");
            version++;
        } while (File.Exists(filePath));

        File.WriteAllText(filePath, json);
        Debug.Log($"Saved User Recording: {filePath}");
    }

}
