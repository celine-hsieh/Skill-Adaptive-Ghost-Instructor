using System.Collections.Generic;
using System.Linq;
using UnityEngine;

[RequireComponent(typeof(Collider))]
public class KeyColliderTrigger : MonoBehaviour
{
    [Header("Audio Settings")]
    [Tooltip("Audio source to play when the key is activated")]
    public PlaySound playSound;

    [Header("Press Settings")]
    [Tooltip("Maximum downward travel distance in local space")]
    public float maxPressDepth = 0.02f;
    [Tooltip("Distance past which the key “activates” and plays audio")]
    public float activationDepth = 0.015f;
    [Tooltip("Speed at which the key returns to its original position (units per second)")]
    public float returnSpeed = 0.05f;
    public float releaseHeight = 0.008f;

    [Header("Linked Logic")]
    public PianoKey keyLogic;

    private Vector3 startPosition;
    private readonly List<Transform> pressingFinger = new();
    private bool hasActivated = false;
    private float currentDeltaY = 0f;

    private bool IsStillColliding => pressingFinger.Count > 0; 
    public float exitGraceTime = 0.05f;

    [Header("Visual Feedback")]
    [Tooltip("Renderer to change color on press")]
    public Renderer keyRenderer;
    public Color normalColor = Color.white;
    public Color pressedColor = Color.red;

    [SerializeField]
    private Transform moveVisualKey;

    private MeshCollider mCollider;

    private void Awake()
    {
        string objectName = gameObject.name; // Match the object name pattern
        string keyName = objectName.Replace(" Collider", "");

        if (moveVisualKey == null)
        {
            moveVisualKey = GameObject.Find(keyName)?.transform;

            if (moveVisualKey == null)
            {
                Debug.LogError($"Object with name '{objectName}' not found.");
                return;
            }
        }

        if (playSound == null)
        {
            string keySoundName = "KeySound." + keyName.Replace(".", "");

            playSound = GameObject.Find(keySoundName).GetComponent<PlaySound>();

            if (playSound == null)
            {
                Debug.LogError($"Object with name '{keySoundName}' not found.");
                return;
            }
        }

        startPosition = moveVisualKey.localPosition;
        if (keyRenderer == null) keyRenderer = moveVisualKey.GetComponent<Renderer>();
        if (keyLogic == null) keyLogic = moveVisualKey.GetComponent<PianoKey>();
        keyRenderer.material.color = normalColor;

        mCollider = GetComponent<MeshCollider>();
        mCollider.convex = true;
        mCollider.isTrigger = true;

    }

    private void Update()
    {
        if (moveVisualKey == null)
        {
            return;
        }

        if (IsStillColliding)
        {

            // Continuously follow the finger's depth
            Bounds meshBounds = mCollider.sharedMesh.bounds;
            float y = pressingFinger.Min(finger => transform.InverseTransformPoint(finger.position).y);
            float deltaY = Mathf.Clamp(y - (moveVisualKey.position.y + 0.5f * meshBounds.size.y), -maxPressDepth, 0f);
            moveVisualKey.localPosition = startPosition + Vector3.up * deltaY;
            currentDeltaY = deltaY;

            if (!hasActivated && deltaY <= -activationDepth)
            {
                hasActivated = true;
                ActivateKey();
            }
        }
        else
        {
            if (hasActivated)
            {
                hasActivated = false;
                if (keyRenderer != null) keyRenderer.material.color = normalColor;
                if (playSound != null)
                {
                    playSound.StopAudioSource();
                }
            }

            // Rebound back
            if (moveVisualKey.localPosition != startPosition)
            {
                moveVisualKey.localPosition = Vector3.MoveTowards(
                    moveVisualKey.localPosition, startPosition, returnSpeed * Time.deltaTime);
            }
        }
    }

    private void ActivateKey()
    {
        if (playSound != null)
        {
            playSound.PlayAudioSource();
        }

        if (keyRenderer != null)
            keyRenderer.material.color = pressedColor;

        foreach (var finger in pressingFinger)
        {
            int fingerId = FindFingerIDFrom(finger);
            if (fingerId >= 0 && keyLogic != null)
                keyLogic.OnPressed(fingerId);
        }
    }

    private int FindFingerIDFrom(Transform finger)
    {
        var id = finger?.GetComponent<FingerIdentifier>() ?? finger?.GetComponentInChildren<FingerIdentifier>();
        return id != null ? id.GetFingerID() : -1;
    }

    private void OnTriggerEnter(Collider other)
    {
        var id = other.GetComponentInParent<FingerIdentifier>();
        if (id == null) return;

        var finger = id.transform;
        if (pressingFinger.Contains(finger))
        {
            throw new System.Exception();
        }

        pressingFinger.Add(finger);

        keyLogic?.HandleFingerEnter(other);
    }

    private void OnTriggerExit(Collider other)
    {
        var identifier = other.GetComponentInParent<FingerIdentifier>();
        if (identifier == null) return;

        var finger = identifier.transform;
        if (!pressingFinger.Contains(finger))
        {
            throw new System.Exception();
        }

        pressingFinger.Remove(finger);
        keyLogic?.HandleFingerExit(other);

    }
}
