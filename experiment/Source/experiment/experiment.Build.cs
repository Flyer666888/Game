using UnrealBuildTool;

public class experiment : ModuleRules
{
	public experiment(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"AIModule",
			"NavigationSystem",
			"EnhancedInput",
			"HeadMountedDisplay",
			"XRBase"
		});
		PrivateDependencyModuleNames.Add("PhysicsCore");
		if (Target.bBuildEditor)
		{
            PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "AssetRegistry", "PhysicsUtilities", "Json", "MeshUtilitiesEngine", "MeshUtilitiesCommon" });
		}
	}
}
