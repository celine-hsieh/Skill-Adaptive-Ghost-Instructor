using TMPro;
using UnityEngine;
using UnityEngine.UI;
using System.Collections;
using System.Runtime.InteropServices;


public class GhostPlaybackSync : MonoBehaviour
{
    public UnityEngine.UI.Slider timeSlider;
    public float animationDuration;
    public float animationTime;
    public int cycleCount;

    public Sprite playIcon;
    public Sprite pauseIcon;
    public Image playPauseImg;

    public bool isPlaying;

    private float animationCycleDuration;

    [Header("Ghost Playback")]
    public PianoGhostPlayer ghostPlayer;
    public GhostChunkController ghostController;

    [Header("Time Labels")]
    public TextMeshProUGUI leftLabel;
    public TextMeshProUGUI rightLabel;

    [Header("Playback Speed")]
    public float playbackSpeed = 0.8f; // default speed
    public Image speedIconImg;
    public Sprite speed1xIcon;
    public Sprite speed08xIcon;
    public Sprite speed05xIcon;
    public Sprite speed02xIcon;

    [HideInInspector]
    public float playbackStartTime;

    private float originalDuration;
    private float previousTime;
    private readonly float[] speedOptions = { 1.0f, 0.8f, 0.5f };
    private int currentSpeedIndex = 0;
    private bool isDragging = false;
    private int extraDelayFrames = 10;
    private float remainingTime;


    private void Start()
    {
        UpdateExtraDelayFrames();
        previousTime = animationTime;
        SetPlaybackSpeed(playbackSpeed);



        if (ghostPlayer != null && ghostPlayer.loadedRecording != null && ghostPlayer.loadedRecording.keyEvents.Count > 0)
        {
            animationDuration = ghostPlayer.loadedRecording.keyEvents[^1].pressTime + 1f;
            timeSlider.maxValue = 1f;
            timeSlider.value = 0f;
            animationTime = 0f;
        }

        if (speedIconImg != null)
        {
            speedIconImg.sprite = speed1xIcon;
        }
    }
    private void UpdateExtraDelayFrames()
    {
        if (ghostPlayer != null && ghostPlayer.Melody == GhostMelodies.C)
        {
            extraDelayFrames = 10;
        }
        else if (ghostPlayer != null && ghostPlayer.Melody == GhostMelodies.B)
        {
            extraDelayFrames = 50;
        }
    }

    public void RestartPlayback()
    {
        playbackStartTime = Time.time;

        previousTime = animationTime;
        animationTime = 1f;
        timeSlider.SetValueWithoutNotify(0f);

        if (ghostPlayer != null)
        {
            ghostPlayer.playbackTime = 0f;
            ghostPlayer.currentIndex = 0;
            ghostPlayer.hasFinished = false;
            ghostPlayer.isPlaying = true;

            if (ghostPlayer.rightHandAnimator != null && ghostPlayer.rightHandAnimator.gameObject.activeInHierarchy)
            {
                ghostPlayer.rightHandAnimator.Update(0f);
                ghostPlayer.rightHandAnimator.Play("HandAnimation3", 0, 0f);
            }

            ghostPlayer.PlayHandAnimations();
        }
        SetPlay();
    }

    public void CyclePlaybackSpeed()
    {
        currentSpeedIndex = (currentSpeedIndex + 1) % speedOptions.Length;
        SetPlaybackSpeed(speedOptions[currentSpeedIndex]);
    }

    public void SetPlaybackSpeed(float speed)
    {
        playbackSpeed = speed;

        // 1) Hand animators
        if (ghostPlayer.rightHandAnimator != null)
            ghostPlayer.rightHandAnimator.speed = speed;
        if (ghostPlayer.leftHandAnimator != null)
            ghostPlayer.leftHandAnimator.speed = speed;

        // 2) All key audio sources (if present on keys)
        foreach (var kv in ghostPlayer.keyMap)
        {
            var audio = kv.Value.GetComponent<AudioSource>();
            if (audio != null)
                audio.pitch = speed;
        }

        // 3) Update UI icon
        if (speedIconImg != null)
        {
            if (Mathf.Approximately(speed, 1.0f)) speedIconImg.sprite = speed1xIcon;
            else if (Mathf.Approximately(speed, 0.8f)) speedIconImg.sprite = speed08xIcon;
            else if (Mathf.Approximately(speed, 0.5f)) speedIconImg.sprite = speed05xIcon;
            else if (Mathf.Approximately(speed, 0.2f)) speedIconImg.sprite = speed02xIcon;
        }
    }

    public void OnSliderValueChange()
    {
        animationTime = timeSlider.value * animationDuration;

        // sync to ghost player
        ghostPlayer.playbackTime = animationTime;

        // set current index to first event after the target time
        var events = ghostPlayer.loadedRecording.keyEvents;
        int idx = events.FindIndex(e => e.pressTime >= animationTime);
        ghostPlayer.currentIndex = idx >= 0 ? idx : events.Count;

        ghostPlayer.hasFinished = false;
        isPlaying = false;
        playPauseImg.sprite = playIcon;

        ApplyCurrentTime();
    }

    public void TogglePlayPause()
    {
        if (isPlaying)
        {
            SetPaused();
        }
        else
        {
            if (Mathf.Abs(animationDuration - animationTime) < 0.1f)
            {
                animationTime = 0.0f;
            }
            else
                ghostPlayer.hasFinished = false;

            if (!ghostPlayer.isPlaying && ghostPlayer.hasFinished)
            {
                RestartPlayback();
            }
            else
            {
                SetPlay();
            }
        }
    }

    public void SetPaused()
    {
        isPlaying = false;
        playPauseImg.sprite = playIcon;
        StopAllCoroutines();
    }

    public void SetPlay()
    {
        isPlaying = true;
        playPauseImg.sprite = pauseIcon;
        if (ghostPlayer.hasFinished == true)
            ghostPlayer.hasFinished = false;
    }

    public void SkipForward5()
    {
        animationTime = Mathf.Min(animationTime + 5f, animationDuration);
        ApplyCurrentTime();
    }

    public void SkipBackward5()
    {
        animationTime = Mathf.Max(animationTime - 5f, 0f);
        ApplyCurrentTime();
    }

    public void OnBeginDrag()
    {
        isDragging = true;
    }

    public void OnEndDrag()
    {
        isDragging = false;
        animationTime = timeSlider.value * animationDuration;
    }

    private string FormatTime(float seconds)
    {
        var mins = seconds / 60.0f;
        var secs = (mins - Mathf.Floor(mins)) * 60.0f;
        mins = Mathf.Floor(mins);

        var iMins = (int)mins;
        var iSecs = (int)secs;

        var secsFormat = iSecs < 10 ? $"0{iSecs}" : $"{iSecs}";
        return $"{iMins}:{secsFormat}";
    }

    private void ApplyCurrentTime()
    {
        // Slider
        if (ghostController != null)
            timeSlider.SetValueWithoutNotify(animationTime / ghostController.finalEndTime);
        else
            timeSlider.SetValueWithoutNotify(animationTime / animationDuration);

        // Ghost player
        ghostPlayer.playbackTime = animationTime;
        ghostPlayer.isPlaying = isPlaying;

        // Animator frame
        if (ghostPlayer.rightHandAnimator != null &&
            ghostPlayer.rightHandAnimator.gameObject.activeInHierarchy)
        {
            float norm = Mathf.Clamp01(animationTime / animationDuration);
            //float realTime = animationTime / animationDuration * originalDuration;
            //float norm = Mathf.Clamp01(realTime / originalDuration);
            ghostPlayer.rightHandAnimator.Play("HandAnimation3", 0, norm);
        }

        // Labels
        leftLabel.SetText(FormatTime(animationTime));
        if (ghostController != null)
            rightLabel.SetText(FormatTime(ghostController.finalEndTime - animationTime));
        else
            rightLabel.SetText(FormatTime(animationDuration - animationTime));
    }

    private void LateUpdate()
    {
        if (ghostPlayer == null || ghostPlayer.loadedRecording == null)
            return;

        // Automatically advance time when playing
        if (isPlaying)
        {
            animationTime += Time.deltaTime * playbackSpeed;

            if (animationTime > animationDuration)
            {
                animationTime = animationDuration;
                SetPaused();
                ghostPlayer.hasFinished = true;
            }
        }

        // Update slider while not dragging
        if (!isDragging)
        {
            if (ghostController != null)
                timeSlider.SetValueWithoutNotify(animationTime / ghostController.finalEndTime);
            else
                timeSlider.SetValueWithoutNotify(animationTime / animationDuration);
        }




        // Play any key sounds for this frame）
        float timeWindowStart = previousTime;
        float timeWindowEnd = animationTime + Time.deltaTime;

        foreach (var keyEvent in ghostPlayer.loadedRecording.keyEvents)
        {
            if (keyEvent.pressTime >= timeWindowStart && keyEvent.pressTime <= timeWindowEnd)
            {
                if (ghostPlayer.keyMap.TryGetValue(keyEvent.keyName, out var key))
                {
                    key.PressForDuration(keyEvent.duration);
                    string sanitizedKeyName = keyEvent.keyName.Replace(".", "");

                    ghostPlayer.PlayKeySound(sanitizedKeyName, keyEvent.duration);
                }
            }

            if (keyEvent.pressTime > timeWindowEnd)
                break;
        }

        // Synchronize ghost playback
        ghostPlayer.isPlaying = isPlaying;
        ghostPlayer.playbackTime = animationTime;

        // Update hand animation frame
        if (ghostPlayer.rightHandAnimator != null && ghostPlayer.rightHandAnimator.gameObject.activeInHierarchy)
        {
            ghostPlayer.rightHandAnimator.Play("HandAnimation3", 0, animationTime / animationDuration);
        }

        // Update time labels
        if (ghostController != null)
            remainingTime = Mathf.Round(ghostController.finalEndTime - animationTime);
        else
            remainingTime = Mathf.Round(animationDuration - animationTime);
        leftLabel.SetText(FormatTime(animationTime));
        rightLabel.SetText(FormatTime(remainingTime));

        previousTime = animationTime;
    }

}