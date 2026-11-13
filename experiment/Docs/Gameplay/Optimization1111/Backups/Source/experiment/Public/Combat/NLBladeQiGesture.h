#pragma once

#include "CoreMinimal.h"

/**
 * Value-only input gate for a button-assisted tracked sword swing.
 * Times use a single, non-negative game-time clock. The owner invalidates this
 * gate when tracking, focus or spatial continuity is lost.
 */
struct FNLBladeQiGestureGate
{
public:
    /** A held button never refreshes the buffer. Invalid presses require release. */
    bool Press(double Now, double BufferSeconds, bool bInputValid)
    {
        if (bButtonHeld) return false;

        bButtonHeld = true;
        bPending = false;
        if (!bInputValid || !IsValidTime(Now) || !FMath::IsFinite(BufferSeconds)
            || BufferSeconds < 0.0 || !FMath::IsFinite(Now + BufferSeconds))
        {
            bReleaseRequired = true;
            return false;
        }

        bReleaseRequired = false;
        PressedAt = Now;
        PendingUntil = Now + BufferSeconds;
        bPending = true;
        return true;
    }

    /** Release cancels an unconsumed press as well as clearing an invalid-input latch. */
    void Release()
    {
        bButtonHeld = false;
        bReleaseRequired = false;
        ClearPending();
    }

    /** An already-held button cannot resume an old request after tracking recovers. */
    void Invalidate()
    {
        bReleaseRequired |= bButtonHeld;
        ClearPending();
    }

    /**
     * Returns true once per press and once per swing identity. Consume before
     * attempting a launch: a cooldown or blocked muzzle must not queue a retry.
     */
    bool TryConsume(double Now, const FGuid& SwingId, bool bSwingActive,
        float SpeedCmPerSec, float ThresholdCmPerSec)
    {
        if (!IsValidTime(Now) || !FMath::IsFinite(SpeedCmPerSec)
            || SpeedCmPerSec < 0.0f || !FMath::IsFinite(ThresholdCmPerSec)
            || ThresholdCmPerSec <= 0.0f || (bPending && Now < PressedAt))
        {
            Invalidate();
            return false;
        }

        if (!HasPending(Now))
        {
            if (bPending && Now > PendingUntil) ClearPending();
            return false;
        }
        if (!bSwingActive || !SwingId.IsValid()) return false;

        if (SwingId == LastConsumedSwing)
        {
            // A second press during the same cut must not spill into the next cut.
            ClearPending();
            return false;
        }
        if (SpeedCmPerSec < ThresholdCmPerSec) return false;

        LastConsumedSwing = SwingId;
        ClearPending();
        return true;
    }

    /** Pure query; an invalid query time cannot mutate the pending request. */
    bool HasPending(double Now) const
    {
        return bPending && bButtonHeld && !bReleaseRequired && IsValidTime(Now)
            && Now >= PressedAt && Now <= PendingUntil;
    }

    bool NeedsRelease() const { return bReleaseRequired; }
    bool IsButtonHeld() const { return bButtonHeld; }

private:
    static bool IsValidTime(double Time)
    {
        return FMath::IsFinite(Time) && Time >= 0.0;
    }

    void ClearPending()
    {
        bPending = false;
        PressedAt = 0.0;
        PendingUntil = 0.0;
    }

    FGuid LastConsumedSwing;
    double PressedAt = 0.0;
    double PendingUntil = 0.0;
    bool bButtonHeld = false;
    bool bReleaseRequired = false;
    bool bPending = false;
};
