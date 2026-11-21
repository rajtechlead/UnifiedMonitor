"""Posture analysis engines.

These modules analyse a normalised inventory snapshot and answer the questions a
CSPM product is expected to answer beyond flat control pass/fail:

* CIS benchmark rule packs per platform (``cis``)
* sensitive-data discovery and exposure (``dspm``)
* effective-permission and privilege-escalation analysis (``ciem``)
* AI deployment inventory and exposure (``aispm``)
* Kubernetes/container posture (``kubernetes``)
* identity-driven attack paths (``paths``)

The engines are pure functions over the snapshot: no cloud credentials are needed
to run them, which is what makes them testable and lets an operator analyse an
exported inventory. The snapshot format is documented in
:mod:`unimonitor.posture.inventory`.
"""

from unimonitor.posture.analysis import analyse
from unimonitor.posture.inventory import normalise

__all__ = ["analyse", "normalise"]
