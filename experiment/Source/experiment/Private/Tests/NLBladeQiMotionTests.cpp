#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLBladeQiGesture.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"

namespace NLBladeQiMotionTests
{
    constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    constexpr float FrameSeconds = 0.016f;
    constexpr float MinimumSpeed = 220.0f;

    /** Real blade samples and input gate, without an XR device or player pawn. */
    class FScopedMotionWorld
    {
    public:
        FScopedMotionWorld()
            : SavedFrameCounter(GFrameCounter)
        {
            if (!GEngine) return;

            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false)
                .RequiresHitProxies(false)
                .CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false)
                .EnableTraceCollision(true)
                .CreateNavigation(false)
                .CreateAISystem(false);
            const FName Name(*FString::Printf(TEXT("NilinBladeQiMotion_%s"),
                *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true,
                ERHIFeatureLevel::Num, &Values);
            if (!World) return;

            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            bHasWorldContext = true;
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();

            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Owner = World->SpawnActor<AActor>(FVector::ZeroVector, FRotator::ZeroRotator, Parameters);
            if (!Owner) return;

            USceneComponent* Root = NewObject<USceneComponent>(Owner);
            Owner->SetRootComponent(Root);
            Owner->AddInstanceComponent(Root);
            Root->RegisterComponent();
            TrackingSpace = AddSceneComponent(Root);
            Weapon = AddSceneComponent(TrackingSpace);
            if (!TrackingSpace || !Weapon) return;
            Weapon->SetRelativeLocation(FVector(0.0, 0.0, 100.0));

            Definition = NewObject<UNLAttackDefinition>(Owner);
            Definition->StableId = TEXT("Test.SwordQi.TrackedMotion");
            Blade = NewObject<UNLBladeComponent>(Owner);
            Owner->AddInstanceComponent(Blade);
            Blade->AttackDefinition = Definition;
            Blade->bEnableTrackedSwing = true;
            Blade->SpeedThresholdCmPerSec = MinimumSpeed;
            Blade->MinSpeedCmPerSecToContinue = 70.0f;
            Blade->RecoverySeconds = 0.22f;
            Blade->MaxSampleGapSeconds = 0.10f;
            Blade->MaxTrackingStepCm = 80.0f;
            Blade->RegisterComponent();
            Blade->ConfigureBlade(Weapon, TrackingSpace);
            Blade->SetTrackedInputValid(true);
            // The fixture advances the world clock, then samples once explicitly.
            Blade->SetComponentTickEnabled(false);
            MotionHandle = Blade->OnTrackedMotionSample.AddLambda(
                [this](const FGuid& SwingId, float Speed, bool bSwingActive)
                {
                    ++SampleCount;
                    LastSwingId = SwingId;
                    LastSpeed = Speed;
                    bLastSwingActive = bSwingActive;
                    if (Gate.TryConsume(World->GetTimeSeconds(), SwingId, bSwingActive, Speed, MinimumSpeed))
                        ++ConsumedCount;
                });
            ResetHandle = Blade->OnHistoryReset.AddLambda([this]()
                {
                    ++ResetCount;
                    Gate.Invalidate();
                });
        }

        ~FScopedMotionWorld()
        {
            if (Blade)
            {
                Blade->OnTrackedMotionSample.Remove(MotionHandle);
                Blade->OnHistoryReset.Remove(ResetHandle);
            }
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                if (GEngine && bHasWorldContext) GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrameCounter;
        }

        FScopedMotionWorld(const FScopedMotionWorld&) = delete;
        FScopedMotionWorld& operator=(const FScopedMotionWorld&) = delete;

        bool IsReady() const
        {
            return World && World->GetPhysicsScene() && World->HasBegunPlay()
                && World->GetSubsystem<UNLCombatResolverSubsystem>() && Owner
                && TrackingSpace && Weapon && Definition && Blade && Blade->IsRegistered();
        }

        bool Press() { return Gate.Press(World->GetTimeSeconds(), 0.25, true); }
        void Release() { Gate.Release(); }

        void Step(float DeltaSeconds = FrameSeconds)
        {
            World->Tick(LEVELTICK_All, DeltaSeconds);
            Blade->TickComponent(DeltaSeconds, LEVELTICK_All, &Blade->PrimaryComponentTick);
            ++GFrameCounter;
        }

        void MoveHand(double DeltaX = 4.0)
        {
            Weapon->SetRelativeLocation(Weapon->GetRelativeLocation() + FVector(DeltaX, 0.0, 0.0));
        }

        void EstablishSettledHand()
        {
            Step(); // First sample is only a baseline.
            Step(); // A stationary tracked sample arms the next swing.
        }

        void WaitForRecovery()
        {
            // Each frame remains below the continuity limit; this includes the
            // first stationary frame that enters the 0.22 second recovery.
            for (int32 Index = 0; Index < 20; ++Index) Step();
        }

        UWorld* World = nullptr;
        AActor* Owner = nullptr;
        USceneComponent* TrackingSpace = nullptr;
        USceneComponent* Weapon = nullptr;
        UNLAttackDefinition* Definition = nullptr;
        UNLBladeComponent* Blade = nullptr;
        FNLBladeQiGestureGate Gate;
        FGuid LastSwingId;
        int32 SampleCount = 0;
        int32 ResetCount = 0;
        int32 ConsumedCount = 0;
        float LastSpeed = 0.0f;
        bool bLastSwingActive = false;

    private:
        USceneComponent* AddSceneComponent(USceneComponent* Parent)
        {
            if (!Parent) return nullptr;
            USceneComponent* Component = NewObject<USceneComponent>(Owner);
            Component->SetupAttachment(Parent);
            Owner->AddInstanceComponent(Component);
            Component->RegisterComponent();
            return Component;
        }

        uint64 SavedFrameCounter = 0;
        bool bHasWorldContext = false;
        FDelegateHandle MotionHandle;
        FDelegateHandle ResetHandle;
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiMotionButtonAndOneCutTest,
    "Nilin.Combat.BladeQi.Motion.ButtonAndOneCut", NLBladeQiMotionTests::TestFlags)

bool FNLBladeQiMotionButtonAndOneCutTest::RunTest(const FString& Parameters)
{
    using namespace NLBladeQiMotionTests;
    FScopedMotionWorld Fixture;
    if (!TestTrue(TEXT("An isolated world has a registered tracked blade"), Fixture.IsReady())) return false;

    TestTrue(TEXT("A valid button press arms before sampling"), Fixture.Press());
    Fixture.Step();
    TestEqual(TEXT("The first sample cannot emit sword qi"), Fixture.ConsumedCount, 0);
    TestEqual(TEXT("The disabled automatic tick cannot double-sample the baseline"), Fixture.SampleCount, 1);
    TestTrue(TEXT("Baseline speed is zero"), FMath::IsNearlyZero(Fixture.LastSpeed));
    TestTrue(TEXT("Baseline has no directional gesture velocity"), Fixture.Blade->CurrentTipVelocity.IsNearlyZero());
    TestFalse(TEXT("A baseline has no active swing"), Fixture.bLastSwingActive);
    Fixture.Step();
    TestEqual(TEXT("A stationary button press still cannot emit sword qi"), Fixture.ConsumedCount, 0);

    Fixture.MoveHand();
    Fixture.Step();
    TestTrue(TEXT("Four centimetres per frame exceeds the real swing threshold"), Fixture.LastSpeed >= MinimumSpeed);
    TestTrue(TEXT("Directional sample measures the same translated tip speed"),
        FMath::IsNearlyEqual(Fixture.Blade->CurrentTipVelocity.Size(), static_cast<double>(Fixture.LastSpeed), 0.1));
    TestTrue(TEXT("Directional sample uses the current valid time step"), Fixture.Blade->GetCurrentMotionSampleSeconds() > 0.0);
    TestTrue(TEXT("Actual blade sampling starts a valid tracked swing"), Fixture.bLastSwingActive && Fixture.LastSwingId.IsValid());
    TestEqual(TEXT("A button plus current-frame swing consumes once"), Fixture.ConsumedCount, 1);
    const FGuid FirstSwing = Fixture.LastSwingId;
    for (int32 Index = 0; Index < 5; ++Index)
    {
        Fixture.MoveHand();
        Fixture.Step();
    }
    TestTrue(TEXT("Continued motion retains one swing identity"), Fixture.LastSwingId == FirstSwing);
    TestEqual(TEXT("Holding through continuous motion cannot repeat"), Fixture.ConsumedCount, 1);
    TestFalse(TEXT("A repeated press while held cannot refresh input"), Fixture.Press());
    Fixture.Release();
    TestTrue(TEXT("A new physical edge may arm during the same cut"), Fixture.Press());
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("A second edge cannot reuse the same cut"), Fixture.ConsumedCount, 1);
    TestFalse(TEXT("A duplicate-cut request is discarded"), Fixture.Gate.HasPending(Fixture.World->GetTimeSeconds()));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiMotionRecoveryTest,
    "Nilin.Combat.BladeQi.Motion.ReleaseAndNewSwing", NLBladeQiMotionTests::TestFlags)

bool FNLBladeQiMotionRecoveryTest::RunTest(const FString& Parameters)
{
    using namespace NLBladeQiMotionTests;
    FScopedMotionWorld Fixture;
    if (!TestTrue(TEXT("The motion fixture is ready"), Fixture.IsReady())) return false;
    Fixture.EstablishSettledHand();
    Fixture.Press();
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("The first tracked cut consumes input"), Fixture.ConsumedCount, 1);
    const FGuid FirstSwing = Fixture.LastSwingId;
    Fixture.Release();
    Fixture.Step();
    TestTrue(TEXT("Stopping below 70 cm/s enters recovery"),
        Fixture.Blade->GetSwingState() == ENLBladeSwingState::Recovery && Fixture.LastSpeed < 70.0f);
    Fixture.WaitForRecovery();
    TestTrue(TEXT("Settling longer than 0.22 seconds restores readiness"), Fixture.Blade->IsReady());
    TestTrue(TEXT("A fresh edge arms the second cut"), Fixture.Press());
    Fixture.MoveHand();
    Fixture.Step();
    TestTrue(TEXT("A new tracked cut has a distinct identity"), Fixture.LastSwingId.IsValid() && Fixture.LastSwingId != FirstSwing);
    TestEqual(TEXT("Release, settle and a fresh swing can fire again"), Fixture.ConsumedCount, 2);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiMotionTrackingSpaceTest,
    "Nilin.Combat.BladeQi.Motion.TrackingSpaceMotionIsExcluded", NLBladeQiMotionTests::TestFlags)

bool FNLBladeQiMotionTrackingSpaceTest::RunTest(const FString& Parameters)
{
    using namespace NLBladeQiMotionTests;
    FScopedMotionWorld Fixture;
    if (!TestTrue(TEXT("The motion fixture is ready"), Fixture.IsReady())) return false;
    Fixture.EstablishSettledHand();
    Fixture.Press();
    Fixture.TrackingSpace->SetRelativeLocationAndRotation(FVector(600.0, -300.0, 100.0), FRotator(0.0, 90.0, 0.0));
    Fixture.Step();
    TestTrue(TEXT("Whole-origin translation and rotation leave hand speed near zero"), Fixture.LastSpeed < 0.1f);
    TestTrue(TEXT("Locomotion cannot become horizontal gesture velocity"), Fixture.Blade->CurrentTipVelocity.Size() < 0.1);
    TestFalse(TEXT("Locomotion does not start a tracked sword cut"), Fixture.bLastSwingActive);
    TestEqual(TEXT("Locomotion plus button does not emit sword qi"), Fixture.ConsumedCount, 0);
    Fixture.TrackingSpace->SetRelativeLocationAndRotation(FVector(-250.0, 400.0, 50.0), FRotator(0.0, -45.0, 0.0));
    Fixture.Step();
    TestTrue(TEXT("A second origin change still excludes world-space blade travel"), Fixture.LastSpeed < 0.1f);
    TestEqual(TEXT("Origin changes cannot consume the request"), Fixture.ConsumedCount, 0);
    TestTrue(TEXT("Ordinary origin motion preserves the short input buffer"), Fixture.Gate.HasPending(Fixture.World->GetTimeSeconds()));
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("Real hand motion in the transformed tracking space can fire"), Fixture.ConsumedCount, 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiMotionDiscontinuityTest,
    "Nilin.Combat.BladeQi.Motion.DiscontinuitiesRequireFreshInput", NLBladeQiMotionTests::TestFlags)

bool FNLBladeQiMotionDiscontinuityTest::RunTest(const FString& Parameters)
{
    using namespace NLBladeQiMotionTests;
    FScopedMotionWorld Fixture;
    if (!TestTrue(TEXT("The motion fixture is ready"), Fixture.IsReady())) return false;
    Fixture.EstablishSettledHand();
    Fixture.Press();
    const int32 BeforeJumpResets = Fixture.ResetCount;
    Fixture.MoveHand(81.0);
    Fixture.Step();
    TestTrue(TEXT("A step beyond 80 cm resets real blade history"), Fixture.ResetCount > BeforeJumpResets);
    TestTrue(TEXT("Tracking jump clears directional gesture velocity"), Fixture.Blade->CurrentTipVelocity.IsNearlyZero());
    TestEqual(TEXT("Tracking jump clears directional sample time"), Fixture.Blade->GetCurrentMotionSampleSeconds(), 0.0);
    TestEqual(TEXT("A tracking jump cannot become a sword-qi swing"), Fixture.ConsumedCount, 0);
    TestFalse(TEXT("The reset callback cancels buffered input"), Fixture.Gate.HasPending(Fixture.World->GetTimeSeconds()));
    TestTrue(TEXT("A held button must be released after a jump"), Fixture.Gate.NeedsRelease());
    Fixture.Step();
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("Motion after the jump cannot reuse the held request"), Fixture.ConsumedCount, 0);
    Fixture.Release();
    Fixture.Press();
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("Release and fresh input recover after the jump"), Fixture.ConsumedCount, 1);

    Fixture.Release();
    Fixture.WaitForRecovery();
    Fixture.Press();
    const int32 BeforeGapResets = Fixture.ResetCount;
    Fixture.MoveHand();
    Fixture.Step(0.15f);
    TestTrue(TEXT("A frame longer than 0.10 seconds resets blade history"), Fixture.ResetCount > BeforeGapResets);
    TestEqual(TEXT("A long frame cannot consume sword-qi input"), Fixture.ConsumedCount, 1);
    TestFalse(TEXT("A long frame clears the pending request"), Fixture.Gate.HasPending(Fixture.World->GetTimeSeconds()));
    TestTrue(TEXT("A held button needs release after a long frame"), Fixture.Gate.NeedsRelease());

    Fixture.Release();
    Fixture.EstablishSettledHand();
    Fixture.Press();
    Fixture.Blade->SetTrackedInputValid(false);
    TestTrue(TEXT("Losing tracking immediately invalidates held input"), Fixture.Gate.NeedsRelease());
    TestFalse(TEXT("Tracking loss clears the short request"), Fixture.Gate.HasPending(Fixture.World->GetTimeSeconds()));
    Fixture.Step();
    Fixture.Blade->SetTrackedInputValid(true);
    Fixture.EstablishSettledHand();
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("Recovered tracking cannot reinterpret a still-held button"), Fixture.ConsumedCount, 1);
    TestFalse(TEXT("Press while held after recovery cannot rearm"), Fixture.Press());
    Fixture.Release();
    TestTrue(TEXT("Release and a new edge arm recovered tracking"), Fixture.Press());
    Fixture.MoveHand();
    Fixture.Step();
    TestEqual(TEXT("A fresh input with recovered real motion can fire"), Fixture.ConsumedCount, 2);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
