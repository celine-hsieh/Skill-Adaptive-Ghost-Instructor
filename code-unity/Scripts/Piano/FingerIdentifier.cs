using UnityEngine;

public class FingerIdentifier : MonoBehaviour
{
    public enum HandSide { Left, Right }
    public enum FingerType { Thumb, Index, Middle, Ring, Pinky }

    public HandSide hand;
    public FingerType finger;

    /// <summary>
    /// right：0–4，left：6–10
    /// </summary>
    public int GetFingerID()
    {
        int baseOffset = hand == HandSide.Left ? 6 : 1;
        return baseOffset + (int)finger;
    }
}
