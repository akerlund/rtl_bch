import cocotb

from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge


_clock_started_for = set()


async def start_clock(dut, period_ns: int = 10):
  """Starts the shared cocotb clock once per simulation.

  Every `@cocotb.test()` in a module runs against the same live simulation,
  so calling this unconditionally from each test would start a second,
  third, ... clock-driving coroutine on the same `clk` signal. Guard on the
  dut identity so only the first call actually starts it.
  """
  key = id(dut)
  if key in _clock_started_for:
    return
  dut.clk.value = 0
  cocotb_clock = Clock(dut.clk, period_ns, unit="ns")
  cocotb.start_soon(cocotb_clock.start())
  _clock_started_for.add(key)


async def reset_dut(dut, ing_bus=None, egr_bus=None, extra_signals=()):
  """Apply the active-low synchronous reset and clear common inputs."""
  dut.rst_n.value = 0

  if ing_bus is not None:
    ing_bus.reset_master()
  if egr_bus is not None:
    egr_bus.reset_slave()
  for name in extra_signals:
    if hasattr(dut, name):
      getattr(dut, name).value = 0

  for _ in range(4):
    await RisingEdge(dut.clk)

  dut.rst_n.value = 1
  await RisingEdge(dut.clk)


async def drive_ingress_and_wait_egress(
  ing_bus, egr_bus, clk, ing_values: dict, egress_fields, timeout: int = 200
):
  """Drives one ingress beat and captures one egress beat over vip_axi4s_if buses.

  ing_bus/egr_bus: Axi4sBus wrappers for the DUT's ing_vif/egr_vif.
  ing_values: signal-name -> value dict driven alongside tvalid on ing_bus.
  egress_fields: signal names captured from egr_bus once egr fires.
  return: dict of captured egress fields.
  """
  egr_bus.drive(tready=1)

  await FallingEdge(clk)
  ing_bus.drive(tvalid=1, **ing_values)

  captured = None
  cycles = 0
  while True:
    await RisingEdge(clk)
    await ReadOnly()
    ing_fire = ing_bus.get("tvalid") and ing_bus.get("tready")
    if egr_bus.get("tvalid") and egr_bus.get("tready"):
      captured = {name: egr_bus.get(name) for name in egress_fields}
    if ing_fire:
      break
    cycles += 1
    if cycles > timeout:
      raise AssertionError("ingress handshake timeout")

  await FallingEdge(clk)
  ing_bus.drive(tvalid=0)

  if captured is not None:
    egr_bus.drive(tready=0)
    return captured

  cycles = 0
  while True:
    await RisingEdge(clk)
    await ReadOnly()
    if egr_bus.get("tvalid") and egr_bus.get("tready"):
      captured = {name: egr_bus.get(name) for name in egress_fields}
      break
    cycles += 1
    if cycles > timeout:
      raise AssertionError("egress handshake timeout")

  await FallingEdge(clk)
  egr_bus.drive(tready=0)
  return captured
