"""Master CV profile — lean port from filling-agent."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl

YearMonth = str  # "YYYY-MM" or the literal "PRESENT"


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class PersonalInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    address: Optional[Address] = None


class SocialLinks(BaseModel):
    linkedin: Optional[HttpUrl] = None
    github: Optional[HttpUrl] = None
    portfolio: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None


class Education(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[YearMonth] = None
    end_date: Optional[YearMonth] = None
    gpa: Optional[float] = None


class WorkExperience(BaseModel):
    company: str
    title: str
    start_date: Optional[YearMonth] = None
    end_date: Optional[YearMonth] = None
    is_current: bool = False
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    url: Optional[HttpUrl] = None


class Skills(BaseModel):
    technical: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class JobPreferences(BaseModel):
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    available_start_date: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    requires_visa_sponsorship: Optional[bool] = None
    work_authorization: Optional[Literal[
        "citizen", "permanent_resident", "work_visa", "student_visa",
        "requires_sponsorship", "other"
    ]] = None
    preferred_work_mode: Optional[Literal["remote", "hybrid", "onsite", "any"]] = None


class CustomResponse(BaseModel):
    question: str
    answer: str
    tags: list[str] = Field(default_factory=list)


class CVProfile(BaseModel):
    schema_version: str = "1.0"
    persona: str = Field("default", description="Allows multi-profile in phase 3.")
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    education: list[Education] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    preferences: JobPreferences = Field(default_factory=JobPreferences)
    custom_responses: list[CustomResponse] = Field(default_factory=list)
