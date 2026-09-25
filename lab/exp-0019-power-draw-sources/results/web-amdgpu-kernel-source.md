# amdgpu: where `power1_input` ("PPT") and `gpu_metrics` come from

- Command: `curl -sfL <URL>` for each file below, then `sed -n` of the lines shown
- Date: 2026-09-25 (accessed)
- Source: Linux kernel tag v7.0 on github.com/torvalds/linux. This machine runs 7.0.0-31-generic (Ubuntu); the Ubuntu tree can differ in detail.
- This machine: `/sys/class/drm/card2/device/ip_discovery/die/0/MP1/*/{major,minor,revision}` = **13.0.5**, GC 10.3.6, and the first 4 bytes of `gpu_metrics` are `120 0 2 1` (size 120, format 2.1).
- Why kept: it shows that a read of these files makes the kernel driver send a message to the SMU.

## 1. hwmon power1_input → sensor GPU_INPUT_POWER → METRICS_CURR_SOCKETPOWER
URL: https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpu/drm/amd/pm/amdgpu_pm.c
```c
static int amdgpu_hwmon_get_power(struct device *dev,
				  enum amd_pp_sensors sensor)
{
	struct amdgpu_device *adev = dev_get_drvdata(dev);
	unsigned int uw;
	u32 query = 0;
	int r;

	r = amdgpu_pm_get_sensor_generic(adev, sensor, (void *)&query);
	if (r)
		return r;

	/* convert to microwatts */
	uw = (query >> 8) * 1000000 + (query & 0xff) * 1000;

	return uw;
}
...
 * - power1_average: average power used by the SoC in microWatts.  On APUs this includes the CPU.
 *
 * - power1_input: instantaneous power used by the SoC in microWatts.  On APUs this includes the CPU.
 *
```

URL: https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpu/drm/amd/pm/swsmu/smu13/smu_v13_0_5_ppt.c
```c
static int smu_v13_0_5_get_smu_metrics_data(struct smu_context *smu,
							MetricsMember_t member,
							uint32_t *value)
{
	struct smu_table_context *smu_table = &smu->smu_table;

	SmuMetrics_t *metrics = (SmuMetrics_t *)smu_table->metrics_table;
	int ret = 0;

	ret = smu_cmn_get_metrics_table(smu, NULL, false);
	if (ret)
...
	case METRICS_CURR_SOCKETPOWER:
		*value = (metrics->CurrentSocketPower << 8) / 1000;
		break;
...
		break;
	case AMDGPU_PP_SENSOR_GPU_INPUT_POWER:
		ret = smu_v13_0_5_get_smu_metrics_data(smu,
								METRICS_CURR_SOCKETPOWER,
								(uint32_t *)data);
		*size = 4;
```

## 2. gpu_metrics fills three power fields, and bypasses the cache
```c
static ssize_t smu_v13_0_5_get_gpu_metrics(struct smu_context *smu,
					   void **table)
{
	struct gpu_metrics_v2_1 *gpu_metrics =
		(struct gpu_metrics_v2_1 *)smu_driver_table_ptr(
			smu, SMU_DRIVER_TABLE_GPU_METRICS);
	SmuMetrics_t metrics;
	int ret = 0;

	ret = smu_cmn_get_metrics_table(smu, &metrics, true);
	if (ret)
		return ret;

	smu_cmn_init_soft_gpu_metrics(gpu_metrics, 2, 1);

	gpu_metrics->temperature_gfx = metrics.GfxTemperature;
	gpu_metrics->temperature_soc = metrics.SocTemperature;

	gpu_metrics->average_gfx_activity = metrics.GfxActivity;
	gpu_metrics->average_mm_activity = metrics.UvdActivity;

	gpu_metrics->average_socket_power = metrics.CurrentSocketPower;
	gpu_metrics->average_gfx_power = metrics.Power[0];
	gpu_metrics->average_soc_power = metrics.Power[1];
	gpu_metrics->average_gfxclk_frequency = metrics.GfxclkFrequency;
```

## 3. The metrics table is fetched by a message to the SMU
URL: https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpu/drm/amd/pm/swsmu/smu_cmn.c
```c
int smu_cmn_get_metrics_table(struct smu_context *smu,
			      void *metrics_table,
			      bool bypass_cache)
{
	struct smu_table_context *smu_table = &smu->smu_table;
	uint32_t table_size =
		smu_table->tables[SMU_TABLE_SMU_METRICS].size;
	int ret = 0;

	if (bypass_cache ||
	    !smu_table->metrics_time ||
	    time_after(jiffies, smu_table->metrics_time + msecs_to_jiffies(1))) {
		ret = smu_cmn_update_table(smu,
				       SMU_TABLE_SMU_METRICS,
				       0,
				       smu_table->metrics_table,
				       false);
		if (ret) {
			dev_info(smu->adev->dev, "Failed to export SMU metrics table!\n");
			return ret;
		}
		smu_table->metrics_time = jiffies;
	}
...
	ret = smu_cmn_send_smc_msg_with_param(smu, drv2smu ?
					  SMU_MSG_TransferTableDram2Smu :
					  SMU_MSG_TransferTableSmu2Dram,
					  table_id | ((argument & 0xFFFF) << 16),
					  NULL);
```

## 4. Units of the SMU table fields
URL: https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpu/drm/amd/pm/swsmu/inc/pmfw_if/smu13_driver_if_v13_0_5.h
```c
99:  uint16_t Power[2];                    //[mW] indices: VDDCR_VDD, VDDCR_SOC
105:  uint16_t CurrentSocketPower;          //[mW]
```

## 5. gpu_metrics_v2_1 layout (power fields at byte 40)
URL: https://raw.githubusercontent.com/torvalds/linux/v7.0/drivers/gpu/drm/amd/include/kgd_pp_interface.h
```c
struct gpu_metrics_v2_1 {
	struct metrics_table_header	common_header;

	/* Temperature */
	uint16_t			temperature_gfx; // gfx temperature on APUs
	uint16_t			temperature_soc; // soc temperature on APUs
	uint16_t			temperature_core[8]; // CPU core temperature on APUs
	uint16_t			temperature_l3[2];

	/* Utilization */
	uint16_t			average_gfx_activity;
	uint16_t			average_mm_activity; // UVD or VCN

	/* Driver attached timestamp (in ns) */
	uint64_t			system_clock_counter;

	/* Power/Energy */
	uint16_t			average_socket_power; // dGPU + APU power on A + A platform
	uint16_t			average_cpu_power;
	uint16_t			average_soc_power;
	uint16_t			average_gfx_power;
	uint16_t			average_core_power[8]; // CPU core power on APUs

```

## What this means
1. Each read of `power1_input` makes the driver send `SMU_MSG_TransferTableSmu2Dram` to the SMU, unless it did so less than 1 ms before. Each read of `gpu_metrics` sends it always (`bypass_cache = true`).
2. The **kernel driver** sends it, under its own lock. This project does not open the SMU. By ADR 0011 section 2 this is "reading what a kernel driver publishes". But the application already causes this message on every pass of its hwmon collector (the amdgpu interval is 0 s). Gova should know this.
3. The kernel converts `CurrentSocketPower` [mW] as `(x << 8) / 1000`, then `(q >> 8) * 1e6 + (q & 0xff) * 1000` µW. For x = 128 this gives 32000 µW = **0.032 W**, which is what hwmon shows on this machine while RAPL shows 161 W.
