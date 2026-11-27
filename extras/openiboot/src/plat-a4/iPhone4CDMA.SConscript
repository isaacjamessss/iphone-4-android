Import('*')

#
# iPhone 4 (CDMA) - iPhone3,3 / n92ap
#
# Shares the A4 (S5L8930) application processor, RAM layout and display
# controller with n90ap (iPhone3,1), but uses a Qualcomm MDM6600 baseband
# instead of the Infineon X-Gold 618 and has a different antenna/board layout.
# Do NOT add the radio-xgold618 module to this target.
#
# MACH_ID 3565 is provisional: it is only used as the Linux ATAG machine
# number, so it does not affect openiboot itself booting. Verify it against
# the n92ap device tree before booting a Linux kernel.
#

iphone_4_cdma_src = [plat_a4_src,
				env.Localize([
				'#audiohw-null.c',
				'accel.c',
				])]
Export('iphone_4_cdma_src')

env = env.Clone()
env.Append(CPPDEFINES=['OPENIBOOT_VERSION_CONFIG=\\" for iPhone 4 (CDMA)\\"', 'MACH_ID=3565'])

env.OpenIBootTarget('iPhone4CDMA', 'iphone_4_cdma_openiboot', 'CONFIG_IPHONE_4_CDMA', iphone_4_cdma_src, None)
