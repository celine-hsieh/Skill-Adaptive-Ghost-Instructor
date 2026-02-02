using UnityEngine;
using System.Collections;
using Oculus.Interaction;
using System.Collections.Generic;

public class PianoKey : MonoBehaviour
{
    private string keyName;
    public PianoGhostRecorder recorder;

    [Header("Ghost Display")]
    private Renderer keyRenderer;
    public Color ghostColor = Color.cyan;
    public Color originalColor;
    // class-level
    private Dictionary<string, float> keyDownTime = new Dictionary<string, float>();
    private Dictionary<string, int> keyDownFinger = new Dictionary<string, int>();
    private PianoGhostPlayer ghost;



    private void Start()
    {
        keyName = gameObject.name;
        ghost = FindObjectOfType<PianoGhostPlayer>();

        if (recorder == null)
        {
            recorder = FindObjectOfType<PianoGhostRecorder>();
        }

        if (keyRenderer == null)
        {
            keyRenderer = GetComponent<Renderer>();
        }

        if (originalColor == Color.clear)
        {
            originalColor = keyRenderer.material.color;
        }
    }

    public void OnPressed(int fingerId)
    {

        if (recorder != null)
        {
            if (recorder.isRecording || recorder.isMeasuring)
            {
                recorder.RecordKeyDown(keyName, fingerId);
            }
        }

        if (ghost != null)
        {
            ghost.RegisterUserKeyPress(new PianoKeyEvent
            {
                keyName = keyName,
                pressTime = Time.time,
                duration = 0.1f,
                finger = fingerId
            });
        }
    }

    public void OnReleased()
    {
        if (recorder != null)
        {
            if (recorder.isRecording || recorder.isMeasuring)
            {
                recorder.RecordKeyUp(keyName);
            }
        }
    }

    public void Flash()
    {
        FlashForDuration(0.3f);
    }

    public void PressForDuration(float duration)
    {
        Debug.Log($"Key {gameObject.name} pressed for {duration} seconds");
        FlashForDuration(duration);
    }

    private Coroutine flashRoutine;

    private void FlashForDuration(float duration)
    {
        if (flashRoutine != null)
        {
            StopCoroutine(flashRoutine);
        }
        flashRoutine = StartCoroutine(FlashCoroutine(duration));
    }

    private IEnumerator FlashCoroutine(float duration)
    {
        keyRenderer.material.color = ghostColor;
        yield return new WaitForSeconds(duration);
        keyRenderer.material.color = originalColor;
        flashRoutine = null;
    }

    public void HandleFingerEnter(Collider other)
    {
        var fingerIdComp = other.GetComponent<FingerIdentifier>()
                         ?? other.GetComponentInChildren<FingerIdentifier>();

        if (fingerIdComp == null) return;

        int fingerId = fingerIdComp.GetFingerID();
        OnPressed(fingerId);
    }

    public void HandleFingerExit(Collider other)
    {
        var fingerIdComp = other.GetComponent<FingerIdentifier>()
                         ?? other.GetComponentInChildren<FingerIdentifier>();

        if (fingerIdComp == null) return;

        OnReleased();
    }


}
