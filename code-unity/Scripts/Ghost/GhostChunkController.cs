using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.IO;
using UnityEngine.UI;
using TMPro;
using Oculus.Interaction;
using System;

[System.Serializable]
public class GhostChunk
{
    public float startTime;
    public float endTime;
}

public class GhostChunkController : MonoBehaviour
{
    [Header("Manual Content Chunks (without gaps)")]
    public List<GhostChunk> manualContentChunks = new List<GhostChunk>();

    [Header("Settings")]
    public float gapDuration = 8f;
    public GhostPlaybackSync playbackSync;
    public PianoGhostPlayer ghostPlayer;
    public GhostHandTransparencyController ghostTransparencyController;

    [Header("UI Elements")]
    public TextMeshPro textPart1;
    public TextMeshPro textPart2;
    public TextMeshPro textWhole;

    [HideInInspector]
    public bool isSeparate = false;
    public bool isLoop = false;
    public float loopInterval = 1f;

    [Header("OVR Poke Interactable")]
    public PokeInteractable pokePart1;
    public PokeInteractable pokePart2;
    public PokeInteractable pokeWhole;

    [Header("Countdown UI")]
    public Canvas countdownCanvas;
    public TextMeshProUGUI countdownText;
    public Transform playerCamera;
    public bool CountdownEnable = true;

    [HideInInspector]
    public int currentChunkIndex = 0;
    [HideInInspector]
    public float finalEndTime { get; private set; }
    [HideInInspector]
    public int playCountPart1 = 0;
    [HideInInspector]
    public int playCountPart2 = 0;
    [HideInInspector]
    public int playCountWhole = 0;
    [HideInInspector]
    public int Count = 0;

    private const int maxPlays = 10;

    private void Awake()
    {
        if (manualContentChunks.Count > 0)
        {
            finalEndTime = manualContentChunks[^1].endTime;
        }
    }

    private void Start()
    {
        if (manualContentChunks.Count > 0 && playbackSync != null)
        {
            SetToChunk(0);
        }
        pokePart2.enabled = false;
        pokeWhole.enabled = false;

        UpdatePlayButton(textPart1, "Phrase 1", maxPlays);
        UpdatePlayButton(textPart2, "Phrase 2", maxPlays);
        UpdatePlayButton(textWhole, "Full Melody", maxPlays);
    }

    private void Update()
    {
        if (playbackSync == null || manualContentChunks.Count == 0)
            return;

        if (!playbackSync.isPlaying)
            return;

        if (isSeparate)
        {
            if (currentChunkIndex < 0 || currentChunkIndex >= manualContentChunks.Count)
                return;

            var chunk = manualContentChunks[currentChunkIndex];
            if (playbackSync.animationTime >= chunk.endTime)
            {
                playbackSync.animationTime = chunk.endTime;
                playbackSync.SetPaused();
            }
        }
        else
        {
            if (playbackSync.animationTime >= finalEndTime)
            {
                playbackSync.animationTime = finalEndTime;
                playbackSync.SetPaused();
            }
        }
    }

    private IEnumerator WaitGapThenNextChunk()
    {
        yield return new WaitForSeconds(gapDuration);
        PlayNextChunk();
    }

    private void UpdatePlayButton(TextMeshPro label, string labelPrefix, int remaining)
    {
        label.text = $"{labelPrefix} ({remaining} left)";
        if (remaining <= 0)
        {
            label.color = Color.gray;
        }
    }

    public void PlayPart1()
    {
        ghostPlayer.CleanUpUserEvents();
        if(ghostTransparencyController != null) { ghostTransparencyController.smoothedError = 0.5f; }
        if (isLoop)
        {
            pokePart2.enabled = false;
            pokePart1.enabled = false;
            pokeWhole.enabled = false;
            StartCoroutine(LoopPlayPart1());
            return;
        }
        else
        {
            if (playCountPart1 >= maxPlays)
            {
                pokePart1.enabled = false;
                Debug.Log("Part 1 reached play limit.");
                return;
            }
            isSeparate = true;
            pokePart1.enabled = true;

            currentChunkIndex = 0;
            SetToChunk(currentChunkIndex);
            playbackSync.SetPlay();

            playCountPart1++;
            int remaining = maxPlays - playCountPart1;
            UpdatePlayButton(textPart1, "Phrase 1", remaining);
        }
    }

    public void PlayPart2()
    {
        ghostPlayer.CleanUpUserEvents();
        if (ghostTransparencyController != null) { ghostTransparencyController.smoothedError = 0.5f; }
        if (isLoop)
        {
            pokePart2.enabled = false;
            pokePart1.enabled = false;
            pokeWhole.enabled = false;
            StartCoroutine(LoopPlayPart2());
            return;
        }
        else
        {
            if (manualContentChunks.Count <= 1 || playCountPart2 >= maxPlays)
            {
                pokePart2.enabled = false;
                return;
            }
            isSeparate = true;
            pokePart2.enabled = true;

            currentChunkIndex = 1;
            SetToChunk(currentChunkIndex);
            playbackSync.SetPlay();

            playCountPart2++;
            int remaining = maxPlays - playCountPart2;
            UpdatePlayButton(textPart2, "Phrase 2", remaining);
        }
    }

    public void PlayWhole()
    {
        ghostPlayer.CleanUpUserEvents();
        if (ghostTransparencyController != null) { ghostTransparencyController.smoothedError = 0.5f; }
        if (isLoop)
        {
            pokeWhole.enabled = false;
            pokePart2.enabled = false;
            pokePart1.enabled = false;
            StartCoroutine(LoopPlayWhole());
            return;
        }
        else
        {
            if (playCountWhole >= maxPlays)
            {
                pokeWhole.enabled = false;
                Debug.Log("Whole play limit reached.");
                return;
            }
            isSeparate = false;
            currentChunkIndex = -1;
            playbackSync.RestartPlayback();

            playCountWhole++;
            int remaining = maxPlays - playCountWhole;
            UpdatePlayButton(textWhole, "Full Melody", remaining);
        }


    }
    private IEnumerator LoopPlayPart1()
    {
        if (playCountPart1 >= maxPlays)
        {
            yield break;
        }

        var chunk = manualContentChunks[0];
        for (int i = 0; i < 10; i++)
        {
            isSeparate = true;
            currentChunkIndex = 0;
            SetToChunk(currentChunkIndex);
            if (CountdownEnable)
            {
                yield return StartCoroutine(ShowCountdownThen(2f));
            }
            playbackSync.SetPlay();

            playCountPart1++;
            int remaining = maxPlays - playCountPart1;
            UpdatePlayButton(textPart1, "Phrase 1", remaining);

            yield return new WaitUntil(() =>
               playbackSync.animationTime >= chunk.endTime || !playbackSync.isPlaying
           );

            yield return new WaitForSeconds(loopInterval);
        }
        pokePart2.enabled = true;
    }
    private IEnumerator LoopPlayPart2()
    {
        if (playCountPart2 >= maxPlays)
        {
            yield break;

        }

        var chunk = manualContentChunks[1];
        for (int i = 0; i < 10; i++)
        {
            isSeparate = true;
            currentChunkIndex = 1;
            SetToChunk(currentChunkIndex);
            if (CountdownEnable)
            {
                yield return StartCoroutine(ShowCountdownThen(2f));
            }
            playbackSync.SetPlay();

            playCountPart2++;
            int remaining = maxPlays - playCountPart2;
            UpdatePlayButton(textPart2, "Phrase 2", remaining);

            yield return new WaitUntil(() =>
                playbackSync.animationTime >= chunk.endTime || !playbackSync.isPlaying
            );

            yield return new WaitForSeconds(loopInterval);
        }
        pokeWhole.enabled = true;
    }

    private IEnumerator LoopPlayWhole()
    {
        if (playCountWhole >= maxPlays)
        {
            yield break;
        }

        for (int i = 0; i < 10; i++)
        {
            isSeparate = false;
            currentChunkIndex = -1;
            if (CountdownEnable)
            {
                yield return StartCoroutine(ShowCountdownThen(2f));
            }
            playbackSync.RestartPlayback();

            playCountWhole++;
            int remaining = maxPlays - playCountWhole;
            UpdatePlayButton(textWhole, "Full Melody", remaining);

            yield return new WaitUntil(() =>
                playbackSync.animationTime >= finalEndTime || !playbackSync.isPlaying
            );

            yield return new WaitForSeconds(loopInterval);
        }
    }

    private IEnumerator PlayTwoChunksSequentially()
    {
        var chunk1 = manualContentChunks[0];
        var chunk2 = manualContentChunks[1];

        // Phrase 1
        SetToChunk(0);
        playbackSync.SetPlay();

        yield return new WaitUntil(() =>
            playbackSync.animationTime >= chunk1.endTime || !playbackSync.isPlaying
        );

        yield return new WaitForSeconds(loopInterval);

        // Phrase 2
        SetToChunk(1);
        playbackSync.SetPlay();

        yield return new WaitUntil(() =>
            playbackSync.animationTime >= chunk2.endTime || !playbackSync.isPlaying
        );

        playCountWhole++;
        int remaining = maxPlays - playCountWhole;
        UpdatePlayButton(textWhole, "Full Melody", remaining);

        pokeWhole.enabled = remaining > 0;
    }

    public void PlayNextChunk()
    {
        if (currentChunkIndex >= manualContentChunks.Count - 1)
            return;

        currentChunkIndex++;
        SetToChunk(currentChunkIndex);
        playbackSync.TogglePlayPause(); // play next chunk
    }

    public void ResetToFirstChunk()
    {
        currentChunkIndex = 0;
        SetToChunk(currentChunkIndex);
        playbackSync.SetPaused();
    }

    private void SetToChunk(int index)
    {
        var chunk = manualContentChunks[index];
        playbackSync.animationTime = chunk.startTime;
        playbackSync.ghostPlayer.playbackTime = chunk.startTime;
        playbackSync.ghostPlayer.currentIndex = playbackSync.ghostPlayer.FindKeyIndex(chunk.startTime);
        playbackSync.timeSlider.SetValueWithoutNotify(chunk.startTime / playbackSync.animationDuration);
        playbackSync.playbackStartTime = Time.time;
    }

    private IEnumerator ShowCountdownThen(float seconds)
    {
        countdownCanvas.gameObject.SetActive(true);

        for (int i = Mathf.CeilToInt(seconds); i > 0; i--)
        {
            countdownText.text = i.ToString();
            yield return new WaitForSeconds(1f);
        }

        countdownCanvas.gameObject.SetActive(false);
    }
}
