#include "Combat/NLBladeQiGesture.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include <limits>

namespace
{
    const FGuid FirstSwing(1, 0, 0, 0);
    const FGuid SecondSwing(2, 0, 0, 0);
    constexpr float SwingThreshold = 220.0f;
    constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiGestureConditionsTest,
    "Nilin.Combat.BladeQi.Gesture.Conditions", TestFlags)

bool FNLBladeQiGestureConditionsTest::RunTest(const FString& Parameters)
{
    FNLBladeQiGestureGate Gate;
    TestFalse(TEXT("A swing without a button cannot fire"), Gate.TryConsume(1.0, FirstSwing, true, 350.0f, SwingThreshold));
    TestTrue(TEXT("A valid button edge arms a short request"), Gate.Press(1.0, 0.25, true));
    TestFalse(TEXT("A stationary blade cannot fire"), Gate.TryConsume(1.01, FirstSwing, true, 0.0f, SwingThreshold));
    TestFalse(TEXT("A slow blade cannot fire"), Gate.TryConsume(1.02, FirstSwing, true, 219.0f, SwingThreshold));
    TestFalse(TEXT("An inactive swing cannot fire"), Gate.TryConsume(1.03, FirstSwing, false, 350.0f, SwingThreshold));
    TestFalse(TEXT("An invalid swing identity cannot fire"), Gate.TryConsume(1.04, FGuid(), true, 350.0f, SwingThreshold));
    TestTrue(TEXT("A threshold-speed active swing consumes the buffered press"), Gate.TryConsume(1.05, FirstSwing, true, SwingThreshold, SwingThreshold));
    TestFalse(TEXT("Consumption removes the request"), Gate.HasPending(1.05));
    TestFalse(TEXT("The consumed request cannot retry a launch"), Gate.TryConsume(1.06, FirstSwing, true, 350.0f, SwingThreshold));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiGestureBufferTest,
    "Nilin.Combat.BladeQi.Gesture.BufferAndRelease", TestFlags)

bool FNLBladeQiGestureBufferTest::RunTest(const FString& Parameters)
{
    FNLBladeQiGestureGate Gate;
    TestTrue(TEXT("A press can precede a new swing"), Gate.Press(2.0, 0.25, true));
    TestTrue(TEXT("The exact buffer deadline is inclusive"), Gate.HasPending(2.25));
    TestTrue(TEXT("A swing at the deadline can fire"), Gate.TryConsume(2.25, FirstSwing, true, 350.0f, SwingThreshold));
    Gate.Release();
    TestTrue(TEXT("A new press arms"), Gate.Press(3.0, 0.25, true));
    TestFalse(TEXT("An expired request is not pending"), Gate.HasPending(3.251));
    TestFalse(TEXT("A late swing cannot fire"), Gate.TryConsume(3.251, SecondSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("Expiry does not turn a held button into a new edge"), Gate.Press(3.26, 0.25, true));
    Gate.Release();
    TestTrue(TEXT("Press after release arms again"), Gate.Press(4.0, 0.25, true));
    Gate.Release();
    TestFalse(TEXT("Release cancels a pending request"), Gate.HasPending(4.01));
    TestFalse(TEXT("A released button cannot fire"), Gate.TryConsume(4.01, SecondSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("Release clears held state"), Gate.IsButtonHeld());

    FNLBladeQiGestureGate ZeroBuffer;
    TestTrue(TEXT("Zero buffer permits same-time input"), ZeroBuffer.Press(0.0, 0.0, true));
    TestTrue(TEXT("Same-time swing can consume a zero buffer"), ZeroBuffer.TryConsume(0.0, FirstSwing, true, 350.0f, SwingThreshold));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiGestureEdgesTest,
    "Nilin.Combat.BladeQi.Gesture.EdgesAndSwingIdentity", TestFlags)

bool FNLBladeQiGestureEdgesTest::RunTest(const FString& Parameters)
{
    FNLBladeQiGestureGate Gate;
    TestTrue(TEXT("First edge arms"), Gate.Press(1.0, 0.2, true));
    TestFalse(TEXT("Repeated press while held cannot refresh"), Gate.Press(1.19, 2.0, true));
    TestFalse(TEXT("The original deadline remains in force"), Gate.HasPending(1.21));
    Gate.Release();
    TestTrue(TEXT("Fresh edge arms"), Gate.Press(2.0, 0.5, true));
    TestTrue(TEXT("First swing consumes"), Gate.TryConsume(2.01, FirstSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("Holding through another swing cannot repeat"), Gate.TryConsume(2.1, SecondSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("Repeated press cannot rearm a held button"), Gate.Press(2.11, 0.5, true));
    Gate.Release();
    TestTrue(TEXT("A second button edge can arm"), Gate.Press(2.12, 0.5, true));
    TestFalse(TEXT("The same swing identity cannot fire twice"), Gate.TryConsume(2.13, FirstSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("A duplicate-swing press is discarded"), Gate.HasPending(2.13));
    TestFalse(TEXT("The duplicate press cannot spill into a later swing"), Gate.TryConsume(2.14, SecondSwing, true, 350.0f, SwingThreshold));
    Gate.Release();
    TestTrue(TEXT("New press can arm a different swing"), Gate.Press(2.2, 0.5, true));
    TestTrue(TEXT("New swing plus new press can fire"), Gate.TryConsume(2.21, SecondSwing, true, 350.0f, SwingThreshold));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiGestureInvalidationTest,
    "Nilin.Combat.BladeQi.Gesture.Invalidation", TestFlags)

bool FNLBladeQiGestureInvalidationTest::RunTest(const FString& Parameters)
{
    FNLBladeQiGestureGate Gate;
    TestFalse(TEXT("An invalid-input press is rejected"), Gate.Press(1.0, 0.3, false));
    TestTrue(TEXT("Invalid input still remembers a held button"), Gate.IsButtonHeld());
    TestTrue(TEXT("Invalid press requires release"), Gate.NeedsRelease());
    TestFalse(TEXT("Input recovery cannot reinterpret the held button"), Gate.Press(1.01, 0.3, true));
    TestFalse(TEXT("Invalid press cannot fire on recovery"), Gate.TryConsume(1.02, FirstSwing, true, 350.0f, SwingThreshold));
    Gate.Release();
    TestFalse(TEXT("Release clears the recovery latch"), Gate.NeedsRelease());
    TestTrue(TEXT("A fresh valid press works"), Gate.Press(2.0, 0.3, true));
    Gate.Invalidate();
    TestTrue(TEXT("Tracking discontinuity while held requires release"), Gate.NeedsRelease());
    TestFalse(TEXT("Discontinuity clears pending input"), Gate.HasPending(2.01));
    TestFalse(TEXT("Discontinuity cannot recover an old request"), Gate.TryConsume(2.02, FirstSwing, true, 350.0f, SwingThreshold));
    Gate.Release();
    TestTrue(TEXT("New edge after discontinuity is accepted"), Gate.Press(3.0, 0.3, true));
    TestTrue(TEXT("Fresh input and swing fire"), Gate.TryConsume(3.01, FirstSwing, true, 350.0f, SwingThreshold));
    Gate.Invalidate();
    Gate.Release();
    TestTrue(TEXT("A new edge can arm after another reset"), Gate.Press(3.02, 0.3, true));
    TestFalse(TEXT("Reset cannot allow reuse of the last consumed swing"), Gate.TryConsume(3.03, FirstSwing, true, 350.0f, SwingThreshold));
    Gate.Release();
    Gate.Invalidate();
    TestFalse(TEXT("Invalidating an unheld button does not require release"), Gate.NeedsRelease());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiGestureInvalidNumbersTest,
    "Nilin.Combat.BladeQi.Gesture.InvalidNumbers", TestFlags)

bool FNLBladeQiGestureInvalidNumbersTest::RunTest(const FString& Parameters)
{
    const double NaN = std::numeric_limits<double>::quiet_NaN();
    const double Infinity = std::numeric_limits<double>::infinity();
    const float FloatNaN = std::numeric_limits<float>::quiet_NaN();
    const float FloatInfinity = std::numeric_limits<float>::infinity();
    const double InvalidPresses[][2] = {
        {-1.0, 0.2}, {NaN, 0.2}, {Infinity, 0.2},
        {1.0, -0.2}, {1.0, NaN}, {1.0, Infinity},
        {std::numeric_limits<double>::max(), std::numeric_limits<double>::max()}
    };
    for (const auto& Input : InvalidPresses)
    {
        FNLBladeQiGestureGate Gate;
        TestFalse(TEXT("Invalid press numbers are rejected"), Gate.Press(Input[0], Input[1], true));
        TestTrue(TEXT("An invalid numeric press still requires release"), Gate.NeedsRelease());
        TestFalse(TEXT("An invalid numeric press cannot fire"), Gate.TryConsume(1.0, FirstSwing, true, 350.0f, SwingThreshold));
    }
    const double InvalidTimes[] = {-1.0, NaN, Infinity};
    for (double Time : InvalidTimes)
    {
        FNLBladeQiGestureGate Gate;
        Gate.Press(1.0, 0.2, true);
        TestFalse(TEXT("Invalid query time cannot report pending"), Gate.HasPending(Time));
        TestTrue(TEXT("An invalid query is read-only"), Gate.HasPending(1.1));
        TestFalse(TEXT("Invalid consume time is rejected"), Gate.TryConsume(Time, FirstSwing, true, 350.0f, SwingThreshold));
        TestFalse(TEXT("Invalid consume time clears pending"), Gate.HasPending(1.1));
        TestTrue(TEXT("Invalid consume requires a fresh button edge"), Gate.NeedsRelease());
    }
    const float InvalidMotion[][2] = {
        {FloatNaN, SwingThreshold}, {FloatInfinity, SwingThreshold}, {-1.0f, SwingThreshold},
        {350.0f, FloatNaN}, {350.0f, FloatInfinity}, {350.0f, 0.0f}, {350.0f, -1.0f}
    };
    for (const auto& Motion : InvalidMotion)
    {
        FNLBladeQiGestureGate Gate;
        Gate.Press(1.0, 0.2, true);
        TestFalse(TEXT("Invalid speed or threshold is rejected"), Gate.TryConsume(1.1, FirstSwing, true, Motion[0], Motion[1]));
        TestTrue(TEXT("Invalid motion requires release"), Gate.NeedsRelease());
    }
    FNLBladeQiGestureGate ClockRollback;
    ClockRollback.Press(2.0, 0.2, true);
    TestFalse(TEXT("Clock rollback cannot consume a later press"), ClockRollback.TryConsume(1.9, FirstSwing, true, 350.0f, SwingThreshold));
    TestFalse(TEXT("Clock rollback discards the request"), ClockRollback.HasPending(2.01));
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
