#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLAbilityComponent.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include <limits>

namespace NLAbilityTests
{
constexpr EAutomationTestFlags Flags=EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter;
struct FBody
{
	AActor* Actor=nullptr;
	UNLCombatIdentityComponent* Identity=nullptr;
	UNLCombatVitalsComponent* Vitals=nullptr;
};
class FWorld
{
public:
	UWorld* World=nullptr; UNLCombatResolverSubsystem* Resolver=nullptr; UNLAbilityComponent* Abilities=nullptr;
	UNLAttackDefinition* Definition=nullptr; FBody Player; uint64 SavedFrame=GFrameCounter;
	FWorld()
	{
		if(!GEngine)return;
		const UWorld::InitializationValues Values=UWorld::InitializationValues().AllowAudioPlayback(false)
			.RequiresHitProxies(false).CreatePhysicsScene(true).ShouldSimulatePhysics(false).EnableTraceCollision(true)
			.CreateNavigation(false).CreateAISystem(false);
		World=UWorld::CreateWorld(EWorldType::Game,false,FName(*FGuid::NewGuid().ToString()),nullptr,true,ERHIFeatureLevel::Num,&Values);
		if(!World)return;
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());World->BeginPlay();
		if(World->GetWorldSettings())World->GetWorldSettings()->NotifyBeginPlay();
		Resolver=World->GetSubsystem<UNLCombatResolverSubsystem>();
		Player=AddBody(ENLCombatFaction::Player,FVector(0,0,100));
		Abilities=NewObject<UNLAbilityComponent>(Player.Actor);Player.Actor->AddInstanceComponent(Abilities);Abilities->RegisterComponent();
		Definition=NewObject<UNLAttackDefinition>(World);Definition->StableId=TEXT("Test.Abilities.Damage");Definition->Damage=10;
	}
	~FWorld(){if(World){World->EndPlay(EEndPlayReason::Quit);if(GEngine)GEngine->DestroyWorldContext(World);World->DestroyWorld(false);}GFrameCounter=SavedFrame;}
	bool Ready()const{return World&&Resolver&&Abilities&&Abilities->HasBegunPlay()&&Player.Identity&&Player.Vitals;}
	FBody AddBody(ENLCombatFaction Faction,FVector Location,bool bCharacter=false)
	{
		FActorSpawnParameters Spawn;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		FBody B;B.Actor=bCharacter?static_cast<AActor*>(World->SpawnActor<ACharacter>(Location,FRotator::ZeroRotator,Spawn))
			:World->SpawnActor<AActor>(Location,FRotator::ZeroRotator,Spawn);
		if(!B.Actor->GetRootComponent())
		{
			USceneComponent* Root=NewObject<USceneComponent>(B.Actor);B.Actor->SetRootComponent(Root);B.Actor->AddInstanceComponent(Root);Root->RegisterComponent();Root->SetWorldLocation(Location);
		}
		B.Identity=NewObject<UNLCombatIdentityComponent>(B.Actor);B.Identity->Faction=Faction;B.Actor->AddInstanceComponent(B.Identity);B.Identity->RegisterComponent();B.Identity->EnsureRuntimeId();
		B.Vitals=NewObject<UNLCombatVitalsComponent>(B.Actor);B.Vitals->DamageProtectionSeconds=0;B.Actor->AddInstanceComponent(B.Vitals);B.Vitals->RegisterComponent();B.Vitals->ResetVitals();
		return B;
	}
	UNLEnemyBrainComponent* AddBrain(const FBody& Body)
	{
		UNLEnemyBrainComponent* Brain=NewObject<UNLEnemyBrainComponent>(Body.Actor);Body.Actor->AddInstanceComponent(Brain);Brain->RegisterComponent();Brain->SetComponentTickEnabled(false);return Brain;
	}
	FNLCombatContact Contact(const FBody& Source,const FBody& Target)const
	{
		FNLCombatContact C;C.AttackInstanceId=FGuid::NewGuid();C.SourceRuntimeId=Source.Identity->EnsureRuntimeId();C.TargetRuntimeId=Target.Identity->EnsureRuntimeId();
		C.AttackDefinitionId=Definition->StableId;C.ContactTimeSeconds=World->GetTimeSeconds();C.HitPosition=Target.Actor->GetActorLocation();return C;
	}
	ANLCombatProjectile* Projectile(const FBody& Source,FVector Position)
	{
		FActorSpawnParameters Spawn;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ANLCombatProjectile* P=World->SpawnActor<ANLCombatProjectile>(Position,FRotator::ZeroRotator,Spawn);
		if(P&&!P->InitializeProjectile(Source.Actor,Definition,FVector::ForwardVector,500,4,5))return nullptr;
		return P;
	}
	void Tick(float Seconds){World->Tick(LEVELTICK_All,Seconds);++GFrameCounter;}
};
}
using namespace NLAbilityTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLPulseCooldownTest,"Nilin.Abilities.Pulse.CooldownPauseAndRetry",Flags)
bool FNLPulseCooldownTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Isolated runtime begins play"),F.Ready()))return false;
	TestTrue(TEXT("Initial pulse activates"),F.Abilities->TryActivatePulse());
	TestTrue(TEXT("GDD 8-second cooldown"),FMath::IsNearlyEqual(F.Abilities->GetPulseCooldownRemaining(),8.f,.01f));
	TestFalse(TEXT("Repeated press rejected"),F.Abilities->TryActivatePulse());
	F.Tick(2);const float Before=F.Abilities->GetPulseCooldownRemaining();
	F.Abilities->SetCombatPaused(true);F.Tick(3);
	TestTrue(TEXT("Local combat pause freezes cooldown"),FMath::IsNearlyEqual(F.Abilities->GetPulseCooldownRemaining(),Before,.01f));
	F.Abilities->SetCombatPaused(false);
	TestTrue(TEXT("Resume does not consume paused time"),FMath::IsNearlyEqual(F.Abilities->GetPulseCooldownRemaining(),Before,.01f));
	FActorSpawnParameters PauserSpawn;PauserSpawn.bDeferConstruction=true;
	APlayerState* Pauser=F.World->SpawnActor<APlayerState>(PauserSpawn);F.World->GetWorldSettings()->SetPauserPlayerState(Pauser);
	F.Tick(2);TestTrue(TEXT("Genuine world pause freezes cooldown"),FMath::IsNearlyEqual(F.Abilities->GetPulseCooldownRemaining(),Before,.01f));
	TestFalse(TEXT("Paused activation rejected"),F.Abilities->TryActivatePulse());
	F.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
	F.Abilities->RestoreAbilityState(27);
	TestEqual(TEXT("Retry restores entry energy"),F.Abilities->GetBurstEnergy(),27.f);
	TestEqual(TEXT("Retry clears transient cooldown"),F.Abilities->GetPulseCooldownRemaining(),0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLPulseHostilityTest,"Nilin.Abilities.Pulse.HostileProjectilesRadiusAndWalls",Flags)
bool FNLPulseHostilityTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Fixture"),F.Ready()))return false;
	const FBody Enemy=F.AddBody(ENLCombatFaction::Enemy,FVector(1000,0,100));
	ANLCombatProjectile* Near=F.Projectile(Enemy,FVector(100,50,100));
	ANLCombatProjectile* Far=F.Projectile(Enemy,FVector(600,0,100));
	ANLCombatProjectile* Friendly=F.Projectile(F.Player,FVector(-100,50,100));
	ANLCombatProjectile* BehindWall=F.Projectile(Enemy,FVector(140,-140,100));
	AActor* Wall=F.World->SpawnActor<AActor>();UBoxComponent* Box=NewObject<UBoxComponent>(Wall);Wall->SetRootComponent(Box);Wall->AddInstanceComponent(Box);
	Box->InitBoxExtent(FVector(10,35,80));Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Box->SetCollisionObjectType(ECC_WorldStatic);Box->SetCollisionResponseToAllChannels(ECR_Ignore);Box->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);Box->RegisterComponent();Box->SetWorldLocation(FVector(70,-70,100));
	if(!TestNotNull(TEXT("Enemy projectile initialized"),Near))return false;
	TestTrue(TEXT("Pulse accepted"),F.Abilities->TryActivatePulse());
	TestTrue(TEXT("Near enemy projectile consumed"),Near->IsActorBeingDestroyed());
	TestFalse(TEXT("Outside-radius projectile survives"),Far->IsActorBeingDestroyed());
	TestFalse(TEXT("Player/reflected projectile survives"),Friendly->IsActorBeingDestroyed());
	TestFalse(TEXT("World wall blocks area clear"),BehindWall->IsActorBeingDestroyed());
	TestEqual(TEXT("Exactly one clear"),F.Abilities->GetLastAbilityResult().ProjectilesCleared,1);
	TestEqual(TEXT("Clearing cannot charge its own burst"),F.Abilities->GetBurstEnergy(),0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLAbilityEnergyTest,"Nilin.Abilities.Burst.ResolverRewardsAndDeduplication",Flags)
bool FNLAbilityEnergyTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Fixture"),F.Ready()))return false;
	const FBody Enemy=F.AddBody(ENLCombatFaction::Enemy,FVector(1000,0,100));
	const FBody Ally=F.AddBody(ENLCombatFaction::Player,FVector(1500,0,100));
	const FNLCombatContact Contact=F.Contact(F.Player,Enemy);
	const FNLCombatResult Hit=F.Resolver->ResolveContact(F.Player.Actor,Enemy.Actor,Contact,F.Definition);
	TestEqual(TEXT("Positive enemy hit earns configured charge"),F.Abilities->GetBurstEnergy(),3.f);
	F.Resolver->ResolveContact(F.Player.Actor,Enemy.Actor,Contact,F.Definition);
	FNLCombatResult Replay=Hit;Replay.ResultId=FGuid::NewGuid();F.Resolver->OnCombatResult.Broadcast(Replay);
	TestEqual(TEXT("Contact/result replay cannot farm energy"),F.Abilities->GetBurstEnergy(),3.f);
	F.Resolver->ResolveContact(F.Player.Actor,Ally.Actor,F.Contact(F.Player,Ally),F.Definition);
	F.Definition->Damage=0;F.Resolver->ResolveContact(F.Player.Actor,Enemy.Actor,F.Contact(F.Player,Enemy),F.Definition);
	TestEqual(TEXT("Friendly or zero-damage contacts give no charge"),F.Abilities->GetBurstEnergy(),3.f);
	F.Definition->Damage=100;const FNLCombatResult Kill=F.Resolver->ResolveContact(F.Player.Actor,Enemy.Actor,F.Contact(F.Player,Enemy),F.Definition);
	TestTrue(TEXT("Resolver records confirmed defeat"),Kill.bTargetDefeated);
	TestEqual(TEXT("First defeat adds a separate 15-point reward"),F.Abilities->GetBurstEnergy(),21.f);
	F.Resolver->OnCombatResult.Broadcast(Kill);
	TestEqual(TEXT("Defeat cannot be rewarded twice"),F.Abilities->GetBurstEnergy(),21.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLAbilityParryEnergyTest,"Nilin.Abilities.Burst.PerfectParryAndPause",Flags)
bool FNLAbilityParryEnergyTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Fixture"),F.Ready()))return false;
	const FBody Enemy=F.AddBody(ENLCombatFaction::Enemy,FVector(1000,0,100));
	UBoxComponent* Barrier=NewObject<UBoxComponent>(F.Player.Actor);Barrier->SetupAttachment(F.Player.Actor->GetRootComponent());Barrier->InitBoxExtent(FVector(10,60,60));F.Player.Actor->AddInstanceComponent(Barrier);Barrier->RegisterComponent();Barrier->SetRelativeLocation(FVector(40,0,0));
	UNLGuardComponent* Guard=NewObject<UNLGuardComponent>(F.Player.Actor);Guard->MaintenanceCostPerSecond=0;Guard->MinimumPerfectRaiseInterval=0;Guard->ReleaseRearmSeconds=0;F.Player.Actor->AddInstanceComponent(Guard);Guard->RegisterComponent();Guard->ConfigureGuard(Barrier,nullptr);
	auto Parry=[&]()
	{
		Guard->SetGuardHeld(false);Guard->SetGuardHeld(true);FNLCombatContact C=F.Contact(Enemy,F.Player);C.HitPosition=Barrier->GetComponentLocation();C.IncomingVelocity=FVector(-1000,0,0);
		return F.Resolver->ResolveGuardContact(Enemy.Actor,F.Player.Actor,C,F.Definition,Guard,false);
	};
	const FNLCombatResult First=Parry();TestTrue(TEXT("Genuine melee perfect parry"),First.Outcome==ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("Perfect parry earns 12"),F.Abilities->GetBurstEnergy(),12.f);
	F.Abilities->SetCombatPaused(true);const FNLCombatResult Paused=Parry();
	TestEqual(TEXT("Locally paused reward consumer cannot charge"),F.Abilities->GetBurstEnergy(),12.f);
	F.Abilities->SetCombatPaused(false);F.Resolver->OnCombatResult.Broadcast(Paused);
	TestEqual(TEXT("Paused event cannot be banked for replay"),F.Abilities->GetBurstEnergy(),12.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLAbilityBurstTest,"Nilin.Abilities.Burst.FullEnergyConsumptionAndDeadGate",Flags)
bool FNLAbilityBurstTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Fixture"),F.Ready()))return false;
	F.Abilities->RestoreAbilityState(99);TestFalse(TEXT("Incomplete charge cannot activate"),F.Abilities->TryActivateBurst());
	TestEqual(TEXT("Failed use does not spend charge"),F.Abilities->GetBurstEnergy(),99.f);
	F.Abilities->RestoreAbilityState(100);TestTrue(TEXT("Full charge activates"),F.Abilities->TryActivateBurst());
	TestEqual(TEXT("Burst spends full charge atomically"),F.Abilities->GetBurstEnergy(),0.f);
	TestFalse(TEXT("Repeated press cannot reuse same charge"),F.Abilities->TryActivateBurst());
	F.Abilities->RestoreAbilityState(100);const FBody Enemy=F.AddBody(ENLCombatFaction::Enemy,FVector(1000,0,100));F.Definition->Damage=100;
	F.Resolver->ResolveContact(Enemy.Actor,F.Player.Actor,F.Contact(Enemy,F.Player),F.Definition);
	TestTrue(TEXT("Player really defeated"),F.Player.Vitals->IsDead());
	TestFalse(TEXT("Dead player cannot pulse"),F.Abilities->TryActivatePulse());
	TestFalse(TEXT("Dead player cannot burst"),F.Abilities->TryActivateBurst());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLAbilityControlTest,"Nilin.Abilities.Control.ResistanceNoNavAndRequestDeduplication",Flags)
bool FNLAbilityControlTest::RunTest(const FString&)
{
	FWorld F;if(!TestTrue(TEXT("Fixture"),F.Ready()))return false;
	const FBody Enemy=F.AddBody(ENLCombatFaction::Enemy,FVector(150,0,100),true);UNLEnemyBrainComponent* Brain=F.AddBrain(Enemy);
	const FBody Boss=F.AddBody(ENLCombatFaction::Enemy,FVector(-150,0,100),true);UNLEnemyBrainComponent* BossBrain=F.AddBrain(Boss);BossBrain->AreaControlResponseScale=0;
	const FBody Ally=F.AddBody(ENLCombatFaction::Player,FVector(0,150,100),true);UNLEnemyBrainComponent* AllyBrain=F.AddBrain(Ally);
	const FVector Start=Enemy.Actor->GetActorLocation();FNLAreaControlRequest Request;Request.AbilityInstanceId=FGuid::NewGuid();
	const FNLAreaControlResult First=F.Resolver->ResolveAreaControl(F.Player.Actor,Request);
	TestTrue(TEXT("Valid control accepted"),First.bAccepted);
	TestTrue(TEXT("Ordinary enemy interrupted"),Brain->GetState()==ENLEnemyState::Staggered);
	TestFalse(TEXT("Attack damage window closed"),Brain->IsAttackWindowActive());
	TestTrue(TEXT("No navigation means no unsafe push"),Enemy.Actor->GetActorLocation().Equals(Start,.01));
	TestFalse(TEXT("Control-immune boss not staggered"),BossBrain->GetState()==ENLEnemyState::Staggered);
	TestFalse(TEXT("Allied character never controlled"),AllyBrain->GetState()==ENLEnemyState::Staggered);
	TestEqual(TEXT("Exactly one enemy interrupted"),First.EnemiesInterrupted,1);
	TestFalse(TEXT("Same ability instance cannot apply twice"),F.Resolver->ResolveAreaControl(F.Player.Actor,Request).bAccepted);
	Request.AbilityInstanceId=FGuid::NewGuid();Request.RadiusCm=std::numeric_limits<float>::quiet_NaN();
	TestFalse(TEXT("Non-finite request rejected"),F.Resolver->ResolveAreaControl(F.Player.Actor,Request).bAccepted);
	return true;
}

#endif
