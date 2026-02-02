using UnityEngine;

public class GhostFollower : MonoBehaviour
{
    [Header("References")]
    public PianoGhostPlayer player;
    public Transform pianoTransform;
    public ObjectTransformController pianoController;

    private Vector3 relativePosition;
    private Quaternion relativeRotation;
    private bool initialized = false;

    void Start()
    {
        if (pianoTransform == null || pianoController == null || player == null)
        {
            return;
        }

        Vector3 pianoInitialPos = pianoController.initialPosition;
        Quaternion pianoInitialRot = Quaternion.Euler(pianoController.initialRotation);

        relativePosition = Quaternion.Inverse(pianoInitialRot) * (transform.position - pianoInitialPos);
        relativeRotation = Quaternion.Inverse(pianoInitialRot) * transform.rotation;

        initialized = true;
    }

    void Update()
    {
        if (!initialized || pianoTransform == null || pianoController == null || player == null)
            return;

        bool shouldShow = player.isPlaying;

        for (int i = 0; i < transform.childCount; i++)
        {
            var child = transform.GetChild(i).gameObject;
            if (child.activeSelf != shouldShow)
                child.SetActive(shouldShow);
        }

        if (!shouldShow)
            return;

        Quaternion pianoCurrentRot = pianoTransform.rotation;
        Vector3 pianoCurrentPos = pianoTransform.position;

        transform.position = pianoCurrentPos + pianoCurrentRot * relativePosition;
        transform.rotation = pianoCurrentRot * relativeRotation;
    }
}
