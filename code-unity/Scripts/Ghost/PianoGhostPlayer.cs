using System.Collections.Generic;
using UnityEngine;
using System.Collections;
using System.IO;
using System;
using System.Text.RegularExpressions;
using System.Linq;

public enum GhostTransparencyPolicy
{
    RuleBasedPolicy,     // RBP
    UtilityDecisionPolicy, // UDP
    SigmoidMappingPolicy, // SMP
    ErrorSensitiveMappingPolicy //ESMP
}

public enum GhostMelodies
{
    A, // static
    B, // UDP
    C  // SMP
}

public class PianoGhostPlayer : MonoBehaviour
{
    [Header("Version number of animation and recording")]
    private string fileName;
    public int version = 1;
    public Animator leftHandAnimator;
    public Animator rightHandAnimator;

    [Header("Ghost Visual Feedback")]
    public GhostHandTransparencyController leftGhostTransparency;
    public GhostHandTransparencyController rightGhostTransparency;


    [Header("Piano References")]
    public Transform pianoTransform;
    public ObjectTransformController pianoController;

    [Header("Ghost Transparency Control")]
    [Range(0f, 1f)]
    public float simulatedErrorRate = 0.5f;
    public GhostTransparencyPolicy transparencyPolicy = GhostTransparencyPolicy.RuleBasedPolicy;
    public GhostMelodies Melody = GhostMelodies.A;
    public bool isDynamicMode = true;
    public bool useSimulatedError = true;

    [HideInInspector]
    public event Action<PianoKeyEvent> OnGhostNotePlayed;

    [HideInInspector]
    public List<PianoKeyEvent> recentUserEvents = new List<PianoKeyEvent>();
    private float userInputWindow = 0.5f;
    private const float MinValidDuration = 0.1f;

    [SerializeField] private float weightPitch = 0.5f;
    [SerializeField] private float weightTiming = 0.1f;
    [SerializeField] private float weightFingering = 0.4f;

    [Header("Audio")]
    private Dictionary<string, AudioSource> keyAudioSources;
    [SerializeField]
    private Transform ghostAudioRoot;

    [HideInInspector]
    public Dictionary<string, PianoKey> keyMap;
    [HideInInspector]
    public PianoGhostRecording loadedRecording;
    private PianoGhostRecording userRecording;
    [HideInInspector]
    public float playbackTime = 0f;
    [HideInInspector]
    public int currentIndex = 0;
    [HideInInspector]
    public bool isPlaying = false;
    [HideInInspector]
    public bool hasFinished = true;
    [HideInInspector]
    public float lastPitchScore;
    [HideInInspector]
    public float lastTimeScore;
    [HideInInspector]
    public float lastFingerScore;
    [HideInInspector]
    public float lastTotalScore;
    [HideInInspector]
    public float lasterrorRate;
    [HideInInspector]
    public float lasttargetAlpha;


    public TogglePianoAudio audioToggleController;

    private Vector3 recordedGhostWorldPosition_L;
    private Vector3 recordedGhostWorldPosition_R;

    private Vector3 initialPosition;
    private Vector3 initialRotation;
    private Vector3 initialScale;

    private Transform leftGhostRoot;
    private Transform rightGhostRoot;
    private float diff;

    void Start()
    {
        StopAllCoroutines();
        Resources.UnloadUnusedAssets();
        System.GC.Collect();
        if (keyMap != null) keyMap.Clear();
        if (loadedRecording != null) loadedRecording.keyEvents.Clear();

        if (pianoController != null)
        {
            initialPosition = pianoController.initialPosition;
            initialRotation = pianoController.initialRotation;
            initialScale = pianoController.initialScale;
        }

        if (leftHandAnimator != null)
            leftGhostRoot = leftHandAnimator.transform;

        if (rightHandAnimator != null)
            rightGhostRoot = rightHandAnimator.transform;

        LoadAnimationClips(version, Melody);
        LoadRecordingFromJson(version, Melody);
        BuildKeyMap();
        BuildKeyAudioSources();
        CleanUpUserEvents();
        hasFinished = true;
    }

    void Update()
    {
        if (isPlaying && loadedRecording != null)
        {
            playbackTime += Time.deltaTime;

            while (currentIndex < loadedRecording.keyEvents.Count &&
                   loadedRecording.keyEvents[currentIndex].pressTime <= playbackTime)
            {
                var keyEvent = loadedRecording.keyEvents[currentIndex];


                float errorRate = useSimulatedError
                    ? simulatedErrorRate
                    : GetPolicyErrorRate(keyEvent);


                if (keyEvent.finger > 5 && leftGhostTransparency != null)
                    leftGhostTransparency.AddErrorRate(errorRate);

                if (keyEvent.finger <= 5 && rightGhostTransparency != null)
                {
                    rightGhostTransparency.AddErrorRate(errorRate);
                }
                OnGhostNotePlayed?.Invoke(keyEvent);


                if (keyMap.TryGetValue(keyEvent.keyName, out var key))
                {
                    key.PressForDuration(keyEvent.duration);

                    string sanitizedKeyName = keyEvent.keyName.Replace(".", ""); // 5.E -> 5E

                    PlayKeySound(sanitizedKeyName, keyEvent.duration);
                }

                currentIndex++;
            }

            if (currentIndex >= loadedRecording.keyEvents.Count)
            {
                isPlaying = false;
                hasFinished = true;
            }
        }

        if (Input.GetKeyDown(KeyCode.R))
        {
            RestartPlayback();
        }
    }

    public void PlayKeySound(string keyName, float duration)
    {
        if (audioToggleController != null && audioToggleController.isMuted)
            return;

        if (keyAudioSources.TryGetValue(keyName, out var source))
        {
            source.Play();
        }
    }


    public void RestartPlayback()
    {

        playbackTime = 0f;
        currentIndex = 0;

        if (rightHandAnimator != null)
        {
            rightHandAnimator.Update(0f);
            rightHandAnimator.Play("HandAnimation3", 0, 0f);
        }

        StopAllCoroutines();
        PlayHandAnimations();
        isPlaying = true;
        hasFinished = false;

    }

    private void LoadAnimationClips(int version, GhostMelodies Melody)
    {
        string leftClipPath = $"./HandMotionClips/Task/Left_HandAnimation_Melody_{Melody}.anim";
        string rightClipPath = $"./HandMotionClips/Task/Right_HandAnimation_Melody_{Melody}.anim";

#if UNITY_EDITOR
        var leftClip = UnityEditor.AssetDatabase.LoadAssetAtPath<AnimationClip>(leftClipPath);
        var rightClip = UnityEditor.AssetDatabase.LoadAssetAtPath<AnimationClip>(rightClipPath);

        if (leftClip != null && leftHandAnimator != null)
        {
            leftHandAnimator.runtimeAnimatorController = CreateOverrideController(leftHandAnimator, "LeftHandAnimation_v1", leftClip);
            Debug.Log($"Loaded left animation clip: {leftClipPath}");
        }

        if (rightClip != null && rightHandAnimator != null)
        {
            rightHandAnimator.runtimeAnimatorController = CreateOverrideController(rightHandAnimator, "HandAnimation3", rightClip);
            Debug.Log($"Loaded right animation clip: {rightClipPath}");
        }
#else
        Debug.LogWarning("Animation clip loading only supported in Unity Editor.");
#endif
    }

#if UNITY_EDITOR
    private RuntimeAnimatorController CreateOverrideController(Animator animator, string originalClipName, AnimationClip newClip)
    {
        var baseController = animator.runtimeAnimatorController as AnimatorOverrideController
                             ?? new AnimatorOverrideController(animator.runtimeAnimatorController);

        var overrides = new List<KeyValuePair<AnimationClip, AnimationClip>>();
        baseController.GetOverrides(overrides);

        for (int i = 0; i < overrides.Count; i++)
        {
            if (overrides[i].Key.name == originalClipName)
            {
                overrides[i] = new KeyValuePair<AnimationClip, AnimationClip>(overrides[i].Key, newClip);
            }
        }

        baseController.ApplyOverrides(overrides);
        return baseController;
    }
#endif



    private void LoadRecordingFromJson(int version, GhostMelodies Melody)
    {
        string fileName = $"ghost_melody_{Melody}.json";
        string path = Path.Combine(Application.dataPath, "PianoKeyEvents", "Task", fileName);
        if (File.Exists(path))
        {
            string json = File.ReadAllText(path);
            loadedRecording = JsonUtility.FromJson<PianoGhostRecording>(json);
            Debug.Log($"Loaded recording file: {path}");
        }
        else
        {
            Debug.LogError($"File not found: {path}");
        }
    }

    private void BuildKeyMap()
    {
        keyMap = new Dictionary<string, PianoKey>();
        var allKeys = FindObjectsOfType<PianoKey>();

        foreach (var key in allKeys)
        {
            string keyNameFromObject = key.gameObject.name;
            if (!string.IsNullOrEmpty(keyNameFromObject) && !keyMap.ContainsKey(keyNameFromObject))
            {
                keyMap[keyNameFromObject] = key;
            }
        }
    }

    private void BuildKeyAudioSources()
    {
        keyAudioSources = new Dictionary<string, AudioSource>();
        var allSources = FindObjectsOfType<AudioSource>();

        foreach (var source in allSources)
        {
            string objName = source.gameObject.name; // eg. KeySound.1C
            if (objName.StartsWith("KeySound."))
            {
                string keyName = objName.Replace("KeySound.", "").Replace(".", ""); // 1C, 2D...

                if (!keyAudioSources.ContainsKey(keyName))
                {
                    var ghostSource = gameObject.AddComponent<AudioSource>();
                    ghostSource.clip = source.clip;
                    ghostSource.volume = source.volume;
                    ghostSource.playOnAwake = false;
                    ghostSource.spatialBlend = 0;
                    ghostSource.outputAudioMixerGroup = source.outputAudioMixerGroup;

                    keyAudioSources[keyName] = ghostSource;
                }
            }
        }
    }

    public void PlayHandAnimations()
    {
        StartCoroutine(PlayAfterAnimatorReady());
    }

    private IEnumerator PlayAfterAnimatorReady()
    {
        // Wait a couple of frames to ensure animators are ready
        yield return null;
        yield return null;
        yield return new WaitForSeconds(0.05f);

        if (leftHandAnimator != null)
            leftHandAnimator.Play("LeftHandAnimation_v1", 0, 0f);

        if (rightHandAnimator != null)
        {
            rightHandAnimator.ResetTrigger("playAnim");
            rightHandAnimator.SetTrigger("playAnim");
        }
    }

    private float EvaluateUserAccuracy(PianoKeyEvent ghostEvent)
    {
        var now = Time.time;
        PianoKeyEvent userEvent = null;
        float minDiff = float.MaxValue;
        float window = userInputWindow;

        foreach (var findUserEvent in recentUserEvents)
        {
            diff = Mathf.Abs(findUserEvent.pressTime - now);
            if (diff < minDiff && diff < window)
            {
                minDiff = diff;
                userEvent = findUserEvent;
            }
        }

        if (userEvent == null)
        {
            Debug.LogWarning("No matching user event found.");
            return 1f;
        }
        else
        {
            Debug.Log($"Matched event: key={userEvent.keyName}, finger={userEvent.finger}, pressTime={userEvent.pressTime}");
        }

        float pitchScore = (userEvent.keyName == ghostEvent.keyName) ? 1f : 0f;
        float timeScore = Mathf.InverseLerp(userInputWindow, 0f, Mathf.Abs(userEvent.pressTime - now));
        float fingerScore = userEvent.finger == ghostEvent.finger ? 1f : 0.5f;

        // weighted sum
        float totalScore =
            pitchScore * weightPitch +
            timeScore * weightTiming +
            fingerScore * weightFingering;

        lastPitchScore = pitchScore;
        lastTimeScore = timeScore;
        lastFingerScore = fingerScore;
        lastTotalScore = totalScore;

        float errorRate = 1f - totalScore;
        lasterrorRate = errorRate;
        return Mathf.Clamp01(errorRate);
    }
    
    private float EvaluateUserAccuracy_RBP(PianoKeyEvent ghostEvent)
    {
        foreach (var findUserEvent in recentUserEvents)
        {
            bool keyCorrect = findUserEvent.keyName == ghostEvent.keyName;
            bool fingerCorrect = findUserEvent.finger == ghostEvent.finger;
            bool timingCorrect = Mathf.Abs(findUserEvent.pressTime - Time.time) < 0.2f;

            if (keyCorrect && fingerCorrect && timingCorrect)
                return 0;
        }

        return 1f;
    }

    private float EvaluateUserAccuracy_UDP(PianoKeyEvent ghostEvent)
    {
        return EvaluateUserAccuracy(ghostEvent);
    }

    private float EvaluateUserAccuracy_SMP(PianoKeyEvent ghostEvent)
    {
        float rawError = EvaluateUserAccuracy_UDP(ghostEvent);
        float sigmoid = 1f / (1f + Mathf.Exp(-10f * (rawError - 0.5f)));
        return sigmoid;
    }

    private float EvaluateUserAccuracy_ESMP(PianoKeyEvent ghostEvent)
    {
        var now = Time.time;
        PianoKeyEvent match = null;
        float minDiff = float.MaxValue;

        foreach (var findUserEvent in recentUserEvents)
        {
            float diff = Mathf.Abs(findUserEvent.pressTime - now);
            if (diff < minDiff)
            {
                minDiff = diff;
                match = findUserEvent;
            }
        }

        if (match == null) return 1f;

        float pitchScore = (match.keyName == ghostEvent.keyName) ? 1f : 0f;
        float timeScore = Mathf.InverseLerp(userInputWindow, 0f, Mathf.Abs(match.pressTime - now));
        float fingerScore = (match.finger == ghostEvent.finger) ? 1f : 0.5f;

        // Error-Sensitivity Mapping (squared weighting for higher sensitivity near 0/1)
        float finalTransparency =
            weightPitch * Mathf.Pow(pitchScore, 2) +
            weightTiming * Mathf.Pow(timeScore, 2) +
            weightFingering * Mathf.Pow(fingerScore, 2);

        return Mathf.Clamp01(finalTransparency);
    }


    public void CleanUpUserEvents()
    {
        recentUserEvents.RemoveAll(e => Time.time - e.pressTime > userInputWindow);
    }

    public void RegisterUserKeyPress(PianoKeyEvent findUserEvent)
    {
        if (recentUserEvents == null)
        {
            recentUserEvents = new List<PianoKeyEvent>();
        }
        recentUserEvents.Add(findUserEvent);
    }

    private float GetPolicyErrorRate(PianoKeyEvent ghostEvent)
    {
        switch (transparencyPolicy)
        {
            case GhostTransparencyPolicy.RuleBasedPolicy:
                return EvaluateUserAccuracy_RBP(ghostEvent);

            case GhostTransparencyPolicy.SigmoidMappingPolicy:
                return EvaluateUserAccuracy_SMP(ghostEvent);

            case GhostTransparencyPolicy.UtilityDecisionPolicy:
                return EvaluateUserAccuracy_UDP(ghostEvent);

            case GhostTransparencyPolicy.ErrorSensitiveMappingPolicy:
                return EvaluateUserAccuracy_ESMP(ghostEvent);

            default:
                return 1f;
        }
    }

}
