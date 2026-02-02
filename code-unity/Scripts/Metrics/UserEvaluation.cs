using Oculus.Interaction.Utils;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[Serializable]
public class ScoreEntry
{
    public float pitchScore;
    public float timeScore;
    public float fingerScore;
    public float totalScore;
    public float errorRate;
    public float targetAlpha;
    public float timestamp;
    public int chunkIndex;
    public int countloop;

    public ScoreEntry(float p, float t, float f, float total, float er, float trans, float time, int chunk, int loop)
    {
        pitchScore = p;
        timeScore = t;
        fingerScore = f;
        totalScore = total;
        errorRate = er;
        totalScore = total;
        timestamp = time;
        chunkIndex = chunk;
        countloop = loop;
        targetAlpha = trans;
    }
}
[Serializable]
public class ScoreHistoryWrapper
{
    public List<ScoreEntry> entries;
}

public class UserEvaluation : MonoBehaviour
{
    [Header("User Info")]
    public bool isMeasuring = false;
    public int userNumber = 1;

    [Header("Score Recording")]
    public bool recordScores = false;
    public float scoreRecordInterval = 0.1f;
    [HideInInspector]
    public bool isGhostPlay = false;

    private bool prevIsMeasuring = false;
    private bool prevRecordScores = false;

    private ScoreEntry[] buffer = new ScoreEntry[2000];
    private int bufferCount = 0;
    private int loop = 0;

    private float _lastTimestamp = -1f;
    private int _lastChunk = -1;
    private int _lastLoop = -1;


    [Header("Target Recorder")]
    public PianoGhostRecorder KeyRecorder;
    public HandAnimationRecorderRuntime HandRecorder;
    public PianoGhostPlayer ghostPlayer;
    public GhostChunkController chunkController;
    public GhostHandTransparencyController ghostHandTransparency;

    void Start()
    {
        if (ghostPlayer == null)
            ghostPlayer = FindObjectOfType<PianoGhostPlayer>();

        ghostPlayer.OnGhostNotePlayed += RecordOneScore;
    }

    void Update()
    {
        // User Record key and hands
        if (KeyRecorder == null || ghostPlayer == null)
            return;

        isGhostPlay = ghostPlayer.isPlaying;

        if (isMeasuring && !prevIsMeasuring)
        {
            Debug.Log($"Start Measuring：User{userNumber}");

            // Key Recording
            KeyRecorder.isMeasuring = true;
            KeyRecorder.userNumber = userNumber;
            KeyRecorder.StartUserRecording();

            // Hand Animation Recording
            HandRecorder.isMeasuring = true;
            HandRecorder.userNumber = userNumber;
        }
        else if (!isMeasuring && prevIsMeasuring)
        {
            Debug.Log($"Stop Measuring：User{userNumber}");

            // Key Recording
            KeyRecorder.isMeasuring = false;
            KeyRecorder.StopAndSaveUserPlay();

            // Hand Animation Recording
            HandRecorder.isMeasuring = false;
        }

        prevIsMeasuring = isMeasuring;


        // User Record Score
        if (recordScores && !prevRecordScores && isGhostPlay)
        {
            bufferCount = 0;
            _lastTimestamp = -1f;
            _lastChunk = -1;
            _lastLoop = -1;

            Debug.Log("Start Score Recording");
            
            ghostPlayer.lastPitchScore = 0f;
            ghostPlayer.lastTimeScore = 0f;
            ghostPlayer.lastFingerScore = 0f;
            ghostPlayer.lastTotalScore = 0f;
        }
        else if (!recordScores && prevRecordScores)
        {
            Debug.Log("Stop Score Recording");
            SaveScoreHistoryAsync();
        }
        prevRecordScores = recordScores;
    }

    void OnDestroy()
    {
        ghostPlayer.OnGhostNotePlayed -= RecordOneScore;
    }

    private void RecordOneScore(PianoKeyEvent ghostEvent)
    {
        if (!recordScores) return;

        int chunk = chunkController?.currentChunkIndex ?? -1;

        if (chunk == 0)
            loop = chunkController.playCountPart1;
        else if (chunk == 1)
            loop = chunkController.playCountPart2;
        else if (chunk == -1)
            loop = chunkController.playCountWhole;

        float timestamp = Time.time;
        // Deduplicate identical entries
        if (Mathf.Approximately(timestamp, _lastTimestamp)
            && chunk == _lastChunk && loop == _lastLoop)
        {
            return;
        }

        Debug.Log($"Recorded score at {timestamp:F2}: total={ghostPlayer.lastTotalScore:F2}");
        buffer[bufferCount++] = new ScoreEntry(
            ghostPlayer.lastPitchScore,
            ghostPlayer.lastTimeScore,
            ghostPlayer.lastFingerScore,
            ghostPlayer.lastTotalScore,
            ghostPlayer.lasterrorRate,
            ghostHandTransparency.lasttargetAlpha,
            Time.time,
            ++chunk,
            loop
        );
    }

    private void SaveScoreHistory()
    {
        var wrapper = new ScoreHistoryWrapper
        {
            entries = new List<ScoreEntry>(bufferCount)
        };
        for (int i = 0; i < bufferCount; i++)
            wrapper.entries.Add(buffer[i]);

        string json = JsonUtility.ToJson(wrapper, true);
        File.WriteAllText(GeneratePath(), json);
        bufferCount = 0;
    }

    private string GeneratePath()
    {
        string folder = Path.Combine(Application.dataPath, "UserPerformanceLogs", $"User{userNumber}");
        if (!Directory.Exists(folder)) Directory.CreateDirectory(folder);
        string baseName = $"User{userNumber}";
        int ver = 1;
        string path;
        do
        {
            path = Path.Combine(folder, $"{baseName}_v{ver++}.json");
        } while (File.Exists(path));
        return path;
    }

    void OnEnable()
    {
        ghostPlayer.OnGhostNotePlayed += RecordOneScore;
    }

    void OnDisable()
    {
        ghostPlayer.OnGhostNotePlayed -= RecordOneScore;
    }

    async void SaveScoreHistoryAsync()
    {
        var wrapper = new ScoreHistoryWrapper2
        {
            entries = new List<ScoreEntry>(bufferCount)
        };
        for (int i = 0; i < bufferCount; i++)
            wrapper.entries.Add(buffer[i]);

        string json = JsonUtility.ToJson(wrapper, true);
        string path = GeneratePath();
        await System.Threading.Tasks.Task.Run(() =>
            File.WriteAllText(path, json)
        );
        bufferCount = 0;
    }
}
