using UnityEngine;

public class PianoKeyTouchListener : MonoBehaviour
{
    private PianoKey pianoKey;

    private Transform currentPressingFinger = null;

    private void Start()
    {
        pianoKey = GetComponentInChildren<PianoKey>();
        if (pianoKey == null)
        {
            Debug.LogWarning("PianoKey not found in children of PianoKeyTouchListener.");
        }
    }

    private void OnTriggerEnter(Collider other)
    {
        if (pianoKey == null || currentPressingFinger != null) return;

        var finger = other.GetComponent<FingerIdentifier>() ?? other.GetComponentInChildren<FingerIdentifier>();
        if (finger != null)
        {
            currentPressingFinger = finger.transform;
            pianoKey.HandleFingerEnter(other);
        }
    }

    private void OnTriggerExit(Collider other)
    {
        if (pianoKey == null || currentPressingFinger == null) return;

        var finger = other.GetComponent<FingerIdentifier>() ?? other.GetComponentInChildren<FingerIdentifier>();
        if (finger != null && finger.transform == currentPressingFinger)
        {
            pianoKey.HandleFingerExit(other);
            currentPressingFinger = null;
        }
    }
}
