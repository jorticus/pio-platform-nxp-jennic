"""
Jennic ZigBee SDK Support
"""

from os.path import join, isdir, exists
import os, shutil, stat

from SCons.Script import Import, SConscript, Builder, AlwaysBuild, Action
from SCons.Script import DefaultEnvironment

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

#Import("env")

env = DefaultEnvironment()
platform = env.PioPlatform()

FRAMEWORK_DIR = platform.get_package_dir("framework-jennic")
TOOLCHAIN_DIR = platform.get_package_dir("toolchain-nxp-beyondstudio")
assert isdir(FRAMEWORK_DIR)
assert isdir(TOOLCHAIN_DIR)

JENNIC_CHIP = env.BoardConfig().get("build.mcu")
if JENNIC_CHIP not in ['JN5161', 'JN5164', 'JN5168', 'JN5169']:
    raise RuntimeError("Invalid CPU selected: {0}".format(JENNIC_CHIP))

JENNIC_CHIP_ID = int(JENNIC_CHIP[2:])  # eg. 5169

JENNIC_CHIP_FAMILY = "JN516x"
JENNIC_CHIP_FAMILY_ID = 5160

# JENNIC_STACK specifies the full stack (MAC only, JenNet-IP, etc.) and
#   determines which set of libraries and include paths are added to the build
JENNIC_STACK = env.GetProjectOption("jennic_stack", "ZLLHA")
assert (JENNIC_STACK in ['ZLLHA', 'ZBPro', 'JIP', 'MAC'])

# JENNIC_MAC allows selection of the MAC layer:
#   MAC         for full MAC
#   MiniMac     for size-optimised variant
#   MiniMacShim for size-optimised with shim to the old API
JENNIC_MAC   = env.GetProjectOption("jennic_mac",   "MiniMacShim")
assert (JENNIC_MAC in ['MAC', 'MiniMac', 'MiniMacShim'])

 # ZCR for Light, ZED for Controller
ZBPRO_DEVICE_TYPE = env.GetProjectOption("zbpro_device_type", None)
assert (ZBPRO_DEVICE_TYPE in ['ZCR', 'ZED'])

# Where to store the non-volatile PDM data
PDM_BUILD_TYPE = env.GetProjectOption("pdm_build_type", 'EEPROM')
assert (PDM_BUILD_TYPE in ['EEPROM','EXTERNAL_FLASH','NONE'])

# If true, the debug lib is linked in
DBG_ENABLE = bool(env.GetProjectOption("jennic_debug_enable", False))
HARDWARE_DEBUG_ENABLED = False

#OPTIONAL_STACK_FEATURES = $(shell $(ZPSCONFIG) -n $(TARGET) -f $(APP_COMMON_SRC_DIR)/$(APP_ZPSCFG) -y )
#OPTIONAL_STACK_FEATURES = 1 # TODO


SDK_STACK_DIR       = join(FRAMEWORK_DIR, "Stack")
SDK_COMPONENTS_DIR  = join(FRAMEWORK_DIR, "Components")
SDK_PLATFORM_DIR    = join(FRAMEWORK_DIR, "Platform")
SDK_CHIP_DIR        = join(FRAMEWORK_DIR, "Chip", JENNIC_CHIP)
SDK_TOOL_DIR        = join(FRAMEWORK_DIR, "Tools")

STACK_SIZE = None
MINIMUM_HEAP_SIZE = None

# NOTE: The following settings are only available for the ZLLHA stack
if JENNIC_STACK == "ZLLHA":

    ZLLHA_FEATURES = env.GetProjectOption("zllha_features", None)
    if not ZLLHA_FEATURES:
        raise Exception("No ZLL/HA features specified")
    
    ZLLHA_FEATURES = [f for f in [f.strip().upper() for f in ZLLHA_FEATURES.split(',')] if f]
    for feature in ZLLHA_FEATURES:
        if feature not in ['ZLL', 'HA_LIGHTING', 'HVAC', 'IAS', 'GREENPOWER', 'ENERGY_AT_HOME', 'MEASUREMENT_AND_SENSING']:
            raise Exception("%s is not a valid ZLL/HA feature" % feature)

    APP_CLUSTER_HA_LIGHTING_SRC     = ('HA_LIGHTING' in ZLLHA_FEATURES)
    APP_CLUSTERS_ENERGY_AT_HOME_SRC = ('ENERGY_AT_HOME' in ZLLHA_FEATURES)
    APP_CLUSTERS_HVAC_SRC           = ('HVAC' in ZLLHA_FEATURES)
    APP_CLUSTERS_IAS_SRC            = ('IAS' in ZLLHA_FEATURES)
    APP_CLUSTER_ZLL_SRC             = ('ZLL' in ZLLHA_FEATURES)
    APP_CLUSTERS_GREENPOWER_SRC     = ('GREENPOWER' in ZLLHA_FEATURES)
    APP_CLUSTERS_MEASUREMENT_AND_SENSING = ('MEASUREMENT_AND_SENSING' in ZLLHA_FEATURES)
    GP_SUPPORT = APP_CLUSTERS_GREENPOWER_SRC 

    if APP_CLUSTER_HA_LIGHTING_SRC and APP_CLUSTER_ZLL_SRC:
        # NOTE: There is a duplicate dimmable_light.h file (one in ZLL, one in HA profile)
        raise Exception("ZLL & HA_LIGHTING features are incompatible")

env.Append(
    ASFLAGS=["-x", "assembler-with-cpp"],

    CCFLAGS=[
        "-Wall",
        "-Wunreachable-code",
    ],

    # NOTE: C++ probably not supported.
    CXXFLAGS=[
        "-fno-rtti",
        "-fno-exceptions",
        "-std=c++11"
    ],

    LINKFLAGS=[
        "-Wl,--gc-sections",
        "-Wl,-u_AppColdStart",
        "-Wl,-u_AppWarmStart",

        # Chip/JNxxxx/Build/config_JNxxxx.mk
        #"-nostartfiles",
        #"-nostdlib",
    ],

    JENNIC_CHIP=JENNIC_CHIP,

    CPPDEFINES=[
        #("F_CPU", "$BOARD_F_CPU"),
        "EMBEDDED",
        "RTOS", # Always tell any actual drivers they're running under an RTOS in this usage

        # This can be used to override the default discovery channel. If not specified, it will be available on all channels
        #("MK_CHANNEL", "0"), 

        # OTA Support
        #"BUILD_OTA",
        #("CLD_OTA_MANF_ID_VALUE", "0x1037"),
        #"OTA_ENCRYPTED",

        "USER_VSR_HANDLER",

        # Chip/Common/Build/config.mk
        ("JENNIC_CHIP", JENNIC_CHIP),
        "JENNIC_CHIP_"+JENNIC_CHIP,
        ("JENNIC_CHIP_FAMILY", JENNIC_CHIP_FAMILY),
        "JENNIC_CHIP_FAMILY_"+JENNIC_CHIP_FAMILY,

        "JENNIC_STACK_"+JENNIC_STACK,
        "JENNIC_MAC_"+JENNIC_MAC,

        # Chip/JNxxxx/Build/config_JNxxxx.mk
        (JENNIC_CHIP_FAMILY,JENNIC_CHIP_FAMILY_ID),
        (JENNIC_CHIP,JENNIC_CHIP_ID),
        ("JENNIC_CHIP_NAME", "_"+JENNIC_CHIP),
        ("JENNIC_CHIP_FAMILY_NAME", "_"+JENNIC_CHIP_FAMILY),

        "WATCHDOG_ENABLED",
        
        # Featureset
        ("JENNIC_HW_BBC_RXINCCA","1"),
        ("JENNIC_HW_BBC_DMA","1"),
        ("JENNIC_HW_BBC_ISA","0"),
        ("JENNIC_SW_EXTERNAL_FLASH","0"),
        ("JN516X_DMA_UART_BACKWARDS_COMPATIBLE_API","1"),
        ("UART_BACKWARDS_COMPATIBLE_API","1"),
        #("PDM_DESCRIPTOR_BASED_API","1"),

        # Platform/Common/Build/config.mk
        ("JENNIC_PCB","DEVKIT4"),
        "JENNIC_PCB_DEVKIT4",
    ],

    CPPPATH=[
        # Hardware Development Platforms
        join(SDK_PLATFORM_DIR, "Common", "Include"),
        join(SDK_PLATFORM_DIR, "DK4", "Include"),

        # Common Stack
        join(SDK_COMPONENTS_DIR, "Common", "Include"),
        join(SDK_COMPONENTS_DIR, "HardwareApi", "Include"),
        join(SDK_COMPONENTS_DIR, "Aes", "Include"),
        join(SDK_COMPONENTS_DIR, "DBG", "Include"),
    ],

    # LIBSOURCE_DIRS=[
    #     join(FRAMEWORK_DIR, "libraries")
    # ],

    LIBPATH=[
        join(SDK_COMPONENTS_DIR, "Library"),
        join(SDK_CHIP_DIR, "Build"),
        join(SDK_PLATFORM_DIR, "DK4", "Library"),
    ],

    JNLIBS=[
        "Aes",
        "HardwareApi",
        "MicroSpecific",
        "Boot",

        "Recal",
        # Platform-specific board library
        "BoardLib"
    ],
    LIBS=[
        'm' # Add math library
    ]
)

if DBG_ENABLE:
    env.Append(
        CPPDEFINES=[
            "DBG_ENABLE"
        ],
        JNLIBS=["DBG"]
    )

if GP_SUPPORT:
    env.Append(CPPDEFINES=["CLD_GREENPOWER"])

#
# Stack Support
#

if JENNIC_MAC == "MAC":
    REDUCED_MAC_LIB_SUFFIX = ''
    if JENNIC_STACK in ['ZLLHA', 'ZBPro']:
        REDUCED_MAC_LIB_SUFFIX = '_ZIGBEE'
        env.Append(CPPDEFINES=["REDUCED_ZIGBEE_MAC_BUILD"])

    env.Append(JNLIBS=[
        "AppApi"+REDUCED_MAC_LIB_SUFFIX,
        "MAC"+REDUCED_MAC_LIB_SUFFIX,
        "TimerServer",
        "TOF",
        "Xcv",
    ])
else:
    if JENNIC_MAC in ["MiniMac","MiniMacShim"]:
        env.Append(JNLIBS=[
            "MiniMac", 
            "MiniMacShim"
        ])
    env.Append(JNLIBS=["MMAC"])

if JENNIC_MAC in ['MiniMacShim','MAC']:
    env.Append(CPPPATH=[
        join(SDK_COMPONENTS_DIR, "AppApi","Include"),
        join(SDK_COMPONENTS_DIR, "MAC", "Include"),
    ])
if JENNIC_MAC in ['MiniMac','MiniMacShim']:
    env.Append(CPPPATH=[
        join(SDK_COMPONENTS_DIR, "MiniMac", "Include"),
    ])
if JENNIC_MAC in ['MiniMac','MiniMacShim', 'MMAC']:
    env.Append(CPPPATH=[
        join(SDK_COMPONENTS_DIR, "MMAC", "Include"),
    ])

#if JENNIC_STACK == "MAC"
if JENNIC_STACK == "JIP":
    env.Append(
        JNLIBS=[
            "PDM_%s" % (PDM_BUILD_TYPE)
        ],
        LINKFLAGS=[
            "-Wl,-ueSecurityTxPrepare",
            "-Wl,-ueSecurityTxEncrypt",
            "-Wl,-ubSecurityRxProcess"
        ])
    LINKER_FILE = 'AppBuildJip'
else:
    LINKER_FILE = 'AppBuildMac'

if JENNIC_STACK in ['ZLLHA', 'ZBPro']:
    OSCONFIG_EXE    = join(SDK_TOOL_DIR, "OSConfig",   "bin", "OSConfig.exe")
    PDUMCONFIG_EXE  = join(SDK_TOOL_DIR, "PDUMConfig", "bin", "PDUMConfig.exe")
    ZPSCONFIG_EXE   = join(SDK_TOOL_DIR, "ZPSConfig",  "bin", "ZPSConfig.exe")
    assert (exists(OSCONFIG_EXE))
    assert (exists(PDUMCONFIG_EXE))
    assert (exists(ZPSCONFIG_EXE))

    PROJ_TARGET = env.GetProjectOption("conf_target", None)
    ZPSCFG_PATH = join('$PROJECT_SRC_DIR', env.GetProjectOption('conf_zps', None)) # app.zpscfg
    OSCFG_PATH = join('$PROJECT_SRC_DIR', env.GetProjectOption('conf_os', None)) # App_ZLL_Light_JN516x.oscfgdiag

    print("Conf Target: %s" % PROJ_TARGET)
    print("Conf ZPS:    %s" % ZPSCFG_PATH)
    print("Conf OS:     %s" % OSCFG_PATH)

    STACK_SIZE = 6000
    MINIMUM_HEAP_SIZE = 2000

    env.Append(
        CPPDEFINES=[
            "PDM_"+PDM_BUILD_TYPE
        ],
        CPPPATH=[
            join(SDK_COMPONENTS_DIR, "MAC", "Include"),
            join(SDK_COMPONENTS_DIR, "MicroSpecific", "Include"),
            join(SDK_COMPONENTS_DIR, "MiniMAC", "Include"),
            join(SDK_COMPONENTS_DIR, "MMAC", "Include"),
            join(SDK_COMPONENTS_DIR, "TimerServer", "Include"),
            join(SDK_COMPONENTS_DIR, "PDM", "Include"),

            join(SDK_COMPONENTS_DIR, "ZPSMAC", "Include"),
            join(SDK_COMPONENTS_DIR, "ZPSNWK", "Include"),
        ],
        JNLIBS=["ZPSAPL"]
    )

    ZPS_APL_LIB = 'ZPSAPL'

    APPLIBS = ["OS", "PWRM", "ZPSTSV", "AES_SW", "PDUM", "ZPSAPL"]
    if JENNIC_CHIP_FAMILY == "JN516x":
        APPLIBS.append("Random")

    #if PDM_BUILD_TYPE in ['EEPROM', 'EXTERNAL_FLASH']:
    #    APPLIBS.append(PDM_BUILD_TYPE)
    if PDM_BUILD_TYPE == 'EEPROM':
        APPLIBS.append('PDM_EEPROM')

    # TODO: Select libraries based on OPTIONAL_STACK_FEATURES
    # For now let's just link in all libraries, even if not needed
    if ZBPRO_DEVICE_TYPE == 'ZCR':
        APPLIBS += ["ZPSNWK", "ZPSZLL", "ZPSGP"]
        ZPS_NWK_LIB = 'ZPSNWK'
    elif ZBPRO_DEVICE_TYPE == 'ZED':
        APPLIBS += ["ZPSNWK_ZED", "ZPSZLL_ZED", "ZPSGP_ZED"]
        ZPS_NWK_LIB = 'ZPSNWK_ZED'

    if JENNIC_MAC == 'MAC':
        APPLIBS.append("ZPSMAC")
    else:
        JENNIC_MAC = 'MiniMacShim' # TODO: This should happen before anything else needs it
        APPLIBS.append("ZPSMAC_Mini")

    if JENNIC_CHIP_FAMILY != 'JN514x':
        env.Append(CPPDEFINES=['PDM_USER_SUPPLIED_ID'])

    env.Append(
        CPPPATH=[join(SDK_COMPONENTS_DIR, appname, "Include") for appname in APPLIBS],
        JNLIBS=APPLIBS
    )

    #
    # Custom build targets
    #

    def get_zpslib_path(name):
        return join(SDK_COMPONENTS_DIR, "Library", "lib%s_%s.a"%(name, JENNIC_CHIP_FAMILY))
    
    BUILDGEN_DIR = '$BUILD_DIR/gen'

    def ClearReadOnlyAttribute(path):
        #print("Clear RO on '%s'" % path)
        try:
            os.chmod(str(path), stat.S_IWRITE)
        except:
            pass

    def GeneratePdumAction(target, source, env):
        action = Action(' '.join([
            '"'+PDUMCONFIG_EXE+'"',
            '-z',PROJ_TARGET,
            '-f','$SOURCES',
            '-o',BUILDGEN_DIR
        ]))
        action(target, source, env)

        for f in target:
            ClearReadOnlyAttribute(f)

    def GenerateOsConfigAction(target, source, env):
        action = Action(' '.join([
            '"'+OSCONFIG_EXE+'"',
            '-f','$SOURCES',
            '-o',BUILDGEN_DIR,
            '-v',JENNIC_CHIP
        ]))
        action(target, source, env)

        for f in target:
            ClearReadOnlyAttribute(f)

    def GenerateZigbeeStackAction(target, source, env):
        action = Action(' '.join([
            '"'+ZPSCONFIG_EXE+'"',
            '-n',PROJ_TARGET,
            '-t',JENNIC_CHIP,
            '-l',get_zpslib_path(ZPS_NWK_LIB),
            '-a',get_zpslib_path(ZPS_APL_LIB),
            '-c',TOOLCHAIN_DIR,
            '-f','$SOURCES',
            '-o',BUILDGEN_DIR
        ]))
        action(target, source, env)

        for f in target:
            ClearReadOnlyAttribute(f)

    env.Append(BUILDERS=dict(
        GeneratePdum=Builder(
            action=env.VerboseAction(GeneratePdumAction, "Generating PDUM Config...")
        ),
        GenerateOsConfig=Builder(
            action=env.VerboseAction(GenerateOsConfigAction, "Generating OS Config...")
        ),
        GenerateZigbeeStack=Builder(
            action=env.VerboseAction(GenerateZigbeeStackAction, "Configuring Zigbee Protocol Stack...")
        )
    ))

    # Generate source/headers from project config
    # These will only be re-generated if the source/dest files change.
    env.GeneratePdum([join(BUILDGEN_DIR, f) for f in [
        'pdum_gen.h',
        'pdum_gen.c',
        'pdum_apdu.S',
    ]], ZPSCFG_PATH)
    env.GenerateOsConfig([join(BUILDGEN_DIR, f) for f in [
        'os_gen.h',
        'os_gen.c',
        'os_irq.S',
        'os_irq_alignment.S',
        'os_irq_buserror.S',
        'os_irq_illegalinstruction.S',
        'os_irq_stackoverflowexception.S',
        'os_irq_unimplementedmodule.S',
    ]], OSCFG_PATH)
    env.GenerateZigbeeStack([join(BUILDGEN_DIR, f) for f in [
        'zps_gen.h',
        'zps_gen.c',
    ]], ZPSCFG_PATH)

    # Compile the generated sources
    genlib = env.StaticLibrary(
        join('$BUILD_DIR', 'Gen'), # output
        [env.File(join(BUILDGEN_DIR,f)) for f in [
            'pdum_gen.c',
            'pdum_apdu.S',
            'os_gen.c',
            'os_irq.S',
            'os_irq_alignment.S',
            'os_irq_buserror.S',
            'os_irq_illegalinstruction.S',
            'os_irq_stackoverflowexception.S',
            'os_irq_unimplementedmodule.S',
            'zps_gen.c'
        ]]
    )
    #includes = env.MatchSourceFiles(env.subst('$PROJECT_INCLUDE_DIR'), ['+<**/os_msg_types.h>'])
    #print("Found os_msg_types.h: %s" % includes)
    env.Prepend(
        CPPPATH=[BUILDGEN_DIR],
        LIBS=[genlib]
    )

    # TODO: We're supposed to feed the above targets in as a pre-action, but I couldn't get this to work...
    #env.AddPreAction('buildprog', target_pdum)

if JENNIC_STACK == 'ZLLHA':
    SDK_ZCL_DIR = join(SDK_COMPONENTS_DIR, "ZCL")
    SDK_ZCL_SRC = join(SDK_ZCL_DIR, "Source")
    SDK_ZCL_CLUSTERS = join(SDK_ZCL_DIR, "Clusters")
    SDK_ZCL_PROFILES = join(SDK_ZCL_DIR, "Profiles")

    env.Append(
        CPPPATH=[
            join(SDK_ZCL_DIR, "Source"),
            join(SDK_ZCL_DIR, "Include"),
            join(SDK_ZCL_CLUSTERS, "General", "Include"),
            join(SDK_ZCL_CLUSTERS, "General", "Source"),
            join(SDK_ZCL_CLUSTERS, "Lighting", "Include"),
            join(SDK_ZCL_CLUSTERS, "MeasurementAndSensing", "Include"),
            join(SDK_ZCL_CLUSTERS, "EnergyAtHome", "Include"),
            join(SDK_ZCL_CLUSTERS, "SE", "Include"),
            join(SDK_ZCL_CLUSTERS, "GreenPower", "Include"),
            join(SDK_ZCL_CLUSTERS, "HVAC", "Include"),
            join(SDK_ZCL_CLUSTERS, "OTA", "Include"),
            join(SDK_ZCL_CLUSTERS, "SmartEnergy", "Include"),
            join(SDK_ZCL_CLUSTERS, "IAS", "Include"),

            join(SDK_ZCL_PROFILES, "HA", "Common", "Include"),
            join(SDK_ZCL_PROFILES, "HA", "Generic", "Include"),

            join(SDK_ZCL_PROFILES, "GP", "Include"),
        ],
        CPPDEFINES=[
            "ZPS_APL_OPT_SINGLE_INSTANCE",
            "OTA_NO_CERTIFICATE",
            "PLME_SAP"
        ],
        LIBPATH=[
            join(SDK_ZCL_DIR, "Build"),
            join(SDK_STACK_DIR, "ZBPro", "Build"),
            join(SDK_STACK_DIR, "ZLLHA", "Build")
        ]
    )

    if APP_CLUSTER_HA_LIGHTING_SRC:
        env.Append(CPPPATH=[join(SDK_ZCL_PROFILES, "HA", "Lighting", "Include"),])
    if APP_CLUSTERS_ENERGY_AT_HOME_SRC:
        env.Append(CPPPATH=[join(SDK_ZCL_PROFILES, "HA", "EnergyAtHome", "Include"),])
    if APP_CLUSTERS_HVAC_SRC:
        env.Append(CPPPATH=[join(SDK_ZCL_PROFILES, "HA", "HVAC", "Include"),])
    if APP_CLUSTERS_IAS_SRC:
        env.Append(CPPPATH=[join(SDK_ZCL_PROFILES, "HA", "IAS", "Include")])

    if APP_CLUSTER_ZLL_SRC:
        env.Append(CPPPATH=[
            join(SDK_ZCL_CLUSTERS, "LightLink", "Include"),
            join(SDK_ZCL_PROFILES, "ZLL", "Include"),
        ])


# Hardware debug support (NOTE: JN516x doesn't need separate library as JTag initialised in bootloader)
if HARDWARE_DEBUG_ENABLED:
    env.Append(LINKFLAGS=[
        "-Wl,--defsym,g_bSWConf_Debug=1",
        #"-Wl,-defsym,g_bSWConf_AltDebugPort=1", # Alt port UART1, else UART0
    ])


# Stack/Common/Build/config.mk
if STACK_SIZE is not None:
    env.Append(LINKFLAGS=["-Wl,--defsym=__stack_size=%d" % STACK_SIZE])
if MINIMUM_HEAP_SIZE is not None:
    env.Append(LINKFLAGS=["-Wl,--defsym,__minimum_heap_size=%d" % MINIMUM_HEAP_SIZE])

# Custom components
# TODO: Automatically populate with all components
env.Append(
    CPPPATH=[
        join(SDK_COMPONENTS_DIR, "Utilities", "Include"),
        join(SDK_COMPONENTS_DIR, "ZCL", "Include"),
        join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "LightLink", "Include"),
        join(SDK_COMPONENTS_DIR, "Xcv", "Include"),
        join(SDK_COMPONENTS_DIR, "Recal", "Include"),
        join(SDK_COMPONENTS_DIR, "OVLY", "Include"),
        join(SDK_COMPONENTS_DIR, "MicroSpecific", "Include"),
    ]
)

# copy CCFLAGS to ASFLAGS (-x assembler-with-cpp mode)
env.Append(ASFLAGS=env.get("CCFLAGS", [])[:])

# Find the appropriate lib for the JNLIBS collection (usually suffixed with the chip family, eg. 'Random_JN516x')
def get_jnlib_fullname(name):
    # These are all the libs with a xxx9 variant:
    if (JENNIC_CHIP == 'JN5169') and (name in ['AppApi', 'HardwareApi', 'MAC', 'MiniMac', 'MMAC', 'Xcv']):
        return '%s_%s' % (name, JENNIC_CHIP)
    if (name in ['JPT']):
        return '%s_%s' % (name, JENNIC_CHIP)
    return '%s_%s' % (name, JENNIC_CHIP_FAMILY)
env.Append(LIBS=[get_jnlib_fullname(lib) for lib in env['JNLIBS']])


# Select correct linker script
if JENNIC_STACK == 'ZLLHA':
    LINKER_FILE = join(SDK_STACK_DIR, "ZLLHA", "Build", "AppBuildZLLHA_"+JENNIC_CHIP)+".ld"
else:
    LINKER_FILE = join(SDK_CHIP_DIR, "Build", "AppBuild%s.ld" % JENNIC_STACK)
if not exists(LINKER_FILE):
    raise RuntimeError('Could not find linker script for stack: %s' % JENNIC_STACK)

env.Replace(LDSCRIPT_PATH=[LINKER_FILE])

print("JENNIC_STACK: %s" % JENNIC_STACK)
print("JENNIC_MAC:   %s" % JENNIC_MAC)
#print("Linker Script: %s", LINKER_FILE)

#print("CFLAGS:  %s" % env['CCFLAGS'])
#print("LDFLAGS: %s" % env['LINKFLAGS'])
#print("DEFINES: %s" % env['CPPDEFINES'])
#print("LIBS:    %s" % env['LIBS'])
print("LIBS:    %s" % env['JNLIBS'])



# TODO: Need to add custom targets for:
# - OSCONFIG   # Configuring the OS ...   (os_gen.c/h, os_irq.S, os_irq_alignment.S, ...)
# - PDUMCONFIG # Configuring the PDUM ... (pdum_gen.c/h)
# - ZPSCONFIG  # Configuring the Zigbee Protocol Stack ...

#
# Target: Build Driver Library
#


libs = []

if JENNIC_STACK == 'ZLLHA':
    # See: Stack\ZLLHA\Build\config_ZLLHA.mk

    # ZCL Source
    libs.append(env.BuildLibrary(
        join("$BUILD_DIR", "ZCL"),
        join(SDK_COMPONENTS_DIR, "ZCL", "Source")
    ))
    libs.append(env.BuildLibrary(
        join("$BUILD_DIR", "ZCL_General"),
        join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "General", "Source")
    ))

    # OTA
    # if APP_CLUSTERS_OTA_SRC:
    #     libs.append(env.BuildLibrary(
    #         join("$BUILD_DIR", "ZCL_OTA"),
    #         join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "OTA", "Source")
    #     ))

    # Zigbee LightLink (ZLL) Stack
    if APP_CLUSTER_ZLL_SRC:
        libs.append(env.BuildLibrary(
            join("$BUILD_DIR", "ZLL"),
            join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "ZLL", "Source")
        ))
        libs.append(env.BuildLibrary(
            join("$BUILD_DIR", "ZLL_Lighting"),
            join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "Lighting", "Source")
        ))
        libs.append(env.BuildLibrary(
            join("$BUILD_DIR", "ZLL_LightLink"),
            join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "LightLink", "Source")
        ))

        # # Measurement And Sensing
        # if APP_CLUSTERS_MEASUREMENT_AND_SENSING:
        #     libs.append(env.BuildLibrary(
        #         join("$BUILD_DIR", "ZCL_MeasurementAndSensing_Cluster"),
        #         join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "MeasurementAndSensing", "Source")
        #     ))

    # HomeAutomation (HA) Stack
    else:
                
        # HA Common
        libs.append(env.BuildLibrary(
            join("$BUILD_DIR", "HA_Common"),
            join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "HA", "Common", "Source")
        ))

        # HA Lighting
        if APP_CLUSTER_HA_LIGHTING_SRC:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_Lighting_Profile"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "HA", "Lighting", "Source")
            ))
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_Lighting_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "Lighting", "Source")
            ))

        # Energy At Home
        if APP_CLUSTERS_ENERGY_AT_HOME_SRC:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_EnergyAtHome_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "EnergyAtHome", "Source")
            ))
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_EnergyAtHome_Profile"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "HA", "EnergyAtHome", "Source")
            ))

        # GreenPower Source
        if APP_CLUSTERS_GREENPOWER_SRC:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_GreenPower_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "GreenPower", "Source")
            ))
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_GreenPower_Profile"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "GP", "Source")
            ))

        # HVAC
        if APP_CLUSTERS_HVAC_SRC:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_HVAC_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "HVAC", "Source")
            ))
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_HVAC_Profile"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "HA", "HVAC", "Source")
            ))

        # IAS
        if APP_CLUSTERS_IAS_SRC:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_IAS_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "IAS", "Source")
            ))
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "HA_IAS_Profile"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Profiles", "HA", "IAS", "Source")
            ))

        if APP_CLUSTERS_MEASUREMENT_AND_SENSING:
            libs.append(env.BuildLibrary(
                join("$BUILD_DIR", "ZCL_MeasurementAndSensing_Cluster"),
                join(SDK_COMPONENTS_DIR, "ZCL", "Clusters", "MeasurementAndSensing", "Source")
            ))

# SDK Source
libs.append(env.BuildLibrary(
    join("$BUILD_DIR", "JNUtilities"),
    join(SDK_COMPONENTS_DIR, "Utilities", "Source")
))

if JENNIC_MAC in ['MiniMacShim'] and JENNIC_CHIP == 'JN5169':
    libs.append(env.BuildLibrary(
        join("$BUILD_DIR", "JNMiniMacShim"),
        join(SDK_COMPONENTS_DIR, "MiniMAC", "Source")
    ))

env.Prepend(LIBS=libs)

