from abc import ABC, abstractmethod
from src.orchestration.state import PipelineState

class BaseAgent(ABC):
    @abstractmethod
    async def process(self, state: PipelineState) -> PipelineState:
        pass

class SourceRegistryAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class DiscoveryAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class CrawlAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class ContentExtractionAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class HiringEventExtractionAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class EligibilityRoleAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class StatusCurrentnessAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class EvidenceValidationAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class ContactIntelligenceAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class PhoneVerificationAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class PersistenceAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state

class TelemetryAgent(BaseAgent):
    async def process(self, state: PipelineState) -> PipelineState:
        return state
