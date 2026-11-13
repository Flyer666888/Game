#include "Combat/NLHorizontalSwordQi.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLHorizontalSwordQiGestureTest,
    "Nilin.Combat.BladeQi.Horizontal.Gesture", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNLHorizontalSwordQiGestureTest::RunTest(const FString& Parameters)
{
    FNLHorizontalSwordQiGesture Gesture;
    const FGuid Swing = FGuid::NewGuid();
    const FVector Right = FVector::RightVector;
    TestFalse(TEXT("A thrust does not trigger a horizontal wave"), Gesture.Sample(Swing, FVector(500, 0, 0), Right, 0.02f, true));
    TestFalse(TEXT("A downward cut does not trigger"), Gesture.Sample(Swing, FVector(0, 0, -500), Right, 0.02f, true));
    TestFalse(TEXT("One small sideways jitter does not trigger"), Gesture.Sample(Swing, FVector(0, 250, 0), Right, 0.01f, true));
    Gesture.Reset();
    TestFalse(TEXT("First five centimetres remain buffered"), Gesture.Sample(Swing, FVector(0, 250, 0), Right, 0.02f, true));
    TestTrue(TEXT("Ten centimetres of a left-to-right cut qualify"), Gesture.Sample(Swing, FVector(0, 250, 0), Right, 0.02f, true));
    Gesture.Reset();
    TestFalse(TEXT("A right-to-left cut also begins accumulation"), Gesture.Sample(Swing, FVector(0, -250, 0), Right, 0.02f, true));
    TestTrue(TEXT("Either cut direction can qualify"), Gesture.Sample(Swing, FVector(0, -250, 0), Right, 0.02f, true));
    Gesture.Reset();
    Gesture.Sample(Swing, FVector(0, 250, 0), Right, 0.02f, true);
    TestFalse(TEXT("Direction reversal cannot combine two jitters"), Gesture.Sample(Swing, FVector(0, -250, 0), Right, 0.02f, true));
    TestFalse(TEXT("Tracking discontinuity resets accumulation"), Gesture.Sample(Swing, FVector(0, -250, 0), Right, 0.2f, true));
    TestFalse(TEXT("The first sample after reset cannot reuse travel"), Gesture.Sample(Swing, FVector(0, -250, 0), Right, 0.02f, true));
    Gesture.Reset();
    const FVector TurnedRight(-1, 0, 0);
    TestTrue(TEXT("The horizontal gesture follows current facing yaw"), Gesture.Sample(Swing, FVector(-500, 0, 0), TurnedRight, 0.02f, true));
    return true;
}
#endif
