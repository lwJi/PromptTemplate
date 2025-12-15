"""Tests for quality scoring."""


from prompt_template import Template
from prompt_template.quality import (
    DimensionScore,
    QualityDimension,
    QualityReport,
    QualityScorer,
)


class TestDimensionScore:
    """Tests for DimensionScore dataclass."""

    def test_dimension_score_creation(self) -> None:
        """Test creating a dimension score."""
        score = DimensionScore(
            dimension=QualityDimension.CLARITY,
            score=85,
            weight=0.25,
            details=["Has role definition", "Clear instructions"],
            suggestions=["Add output format"],
        )

        assert score.dimension == QualityDimension.CLARITY
        assert score.score == 85
        assert score.weight == 0.25
        assert len(score.details) == 2
        assert len(score.suggestions) == 1


class TestQualityReport:
    """Tests for QualityReport dataclass."""

    def test_is_production_ready_threshold(self) -> None:
        """Test production-ready threshold."""
        # Score >= 70 is production ready
        ready_report = QualityReport(
            template_name="test",
            overall_score=70,
            grade="C",
        )
        assert ready_report.is_production_ready is True

        not_ready_report = QualityReport(
            template_name="test",
            overall_score=69,
            grade="D",
        )
        assert not_ready_report.is_production_ready is False

    def test_format_report(self) -> None:
        """Test report formatting."""
        report = QualityReport(
            template_name="test-template",
            overall_score=85,
            grade="B",
            dimensions={
                QualityDimension.CLARITY: DimensionScore(
                    dimension=QualityDimension.CLARITY,
                    score=90,
                    weight=0.25,
                    details=["Good role definition"],
                    suggestions=[],
                )
            },
            summary="Good quality template.",
            top_suggestions=["Consider adding more details"],
        )

        formatted = report.format_report()

        assert "test-template" in formatted
        assert "85" in formatted
        assert "Grade: B" in formatted
        assert "Clarity" in formatted


class TestQualityScorer:
    """Tests for QualityScorer class."""

    def test_score_high_quality_template(self) -> None:
        """Test scoring a high-quality template."""
        scorer = QualityScorer()

        template = Template.from_dict({
            "name": "well-designed",
            "description": "A well-documented template for code review.",
            "tags": ["code", "review"],
            "system_prompt": """
            <role>
            You are an expert code reviewer with deep knowledge of software engineering.
            </role>

            <guidelines>
            - Be thorough but constructive
            - Focus on code quality and maintainability
            </guidelines>
            """,
            "user_prompt": """
            <task>
            Please review the following code for issues and improvements.
            </task>

            <code>
            {{code}}
            </code>

            <output_format>
            Provide your review in this structure:
            1. Summary
            2. Issues found
            3. Suggestions
            </output_format>
            """,
            "variables": [
                {
                    "name": "code",
                    "type": "string",
                    "required": True,
                    "description": "The source code to review for quality issues",
                }
            ],
        })

        report = scorer.score(template.config)

        assert report.overall_score >= 70
        assert report.grade in ["A", "B", "C"]
        assert report.is_production_ready

    def test_score_low_quality_template(self) -> None:
        """Test scoring a template with quality issues."""
        scorer = QualityScorer()

        template = Template.from_dict({
            "name": "minimal",
            "template": "{{x}}",  # Minimal, no structure
            "variables": [{"name": "x", "type": "string"}],  # No description
        })

        report = scorer.score(template.config)

        # Minimal template won't get the highest grade
        assert report.grade != "A"
        # Should have suggestions for improvement
        assert len(report.top_suggestions) > 0
        # Clarity should be low (no role, no task, no output format)
        assert report.dimensions[QualityDimension.CLARITY].score < 70

    def test_all_dimensions_scored(self) -> None:
        """Test that all dimensions are scored."""
        scorer = QualityScorer()

        template = Template.from_dict({
            "name": "test",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string"}],
        })

        report = scorer.score(template.config)

        assert QualityDimension.CLARITY in report.dimensions
        assert QualityDimension.CONSISTENCY in report.dimensions
        assert QualityDimension.COMPLETENESS in report.dimensions
        assert QualityDimension.EFFICIENCY in report.dimensions
        assert QualityDimension.STRUCTURE in report.dimensions

    def test_dimension_weights_sum_to_one(self) -> None:
        """Test that dimension weights sum to 1.0."""
        total_weight = sum(QualityScorer.DIMENSION_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_grade_thresholds(self) -> None:
        """Test grade assignment based on score."""
        scorer = QualityScorer()

        # Create templates that should result in different grades
        template = Template.from_dict({
            "name": "test",
            "template": "Hello!",
        })

        report = scorer.score(template.config)

        # Verify grade matches score threshold
        if report.overall_score >= 90:
            assert report.grade == "A"
        elif report.overall_score >= 80:
            assert report.grade == "B"
        elif report.overall_score >= 70:
            assert report.grade == "C"
        elif report.overall_score >= 60:
            assert report.grade == "D"
        else:
            assert report.grade == "F"

    def test_clarity_score_role_detection(self) -> None:
        """Test clarity score detects role definition."""
        scorer = QualityScorer()

        with_role = Template.from_dict({
            "name": "with-role",
            "template": "You are an expert. Help with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        without_role = Template.from_dict({
            "name": "without-role",
            "template": "Help with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        with_role_report = scorer.score(with_role.config)
        without_role_report = scorer.score(without_role.config)

        with_role_clarity = with_role_report.dimensions[QualityDimension.CLARITY].score
        without_role_clarity = without_role_report.dimensions[
            QualityDimension.CLARITY
        ].score

        assert with_role_clarity > without_role_clarity

    def test_consistency_score_naming(self) -> None:
        """Test consistency score checks naming conventions."""
        scorer = QualityScorer()

        consistent = Template.from_dict({
            "name": "consistent",
            "template": "{{user_name}} and {{user_email}}",
            "variables": [
                {"name": "user_name", "type": "string"},
                {"name": "user_email", "type": "string"},
            ],
        })

        inconsistent = Template.from_dict({
            "name": "inconsistent",
            "template": "{{user_name}} and {{userEmail}}",
            "variables": [
                {"name": "user_name", "type": "string"},
                {"name": "userEmail", "type": "string"},
            ],
        })

        consistent_report = scorer.score(consistent.config)
        inconsistent_report = scorer.score(inconsistent.config)

        consistent_score = consistent_report.dimensions[
            QualityDimension.CONSISTENCY
        ].score
        inconsistent_score = inconsistent_report.dimensions[
            QualityDimension.CONSISTENCY
        ].score

        assert consistent_score > inconsistent_score

    def test_completeness_score_description(self) -> None:
        """Test completeness score checks for description."""
        scorer = QualityScorer()

        with_desc = Template.from_dict({
            "name": "with-desc",
            "description": "A detailed description of what this template does.",
            "template": "Hello!",
        })

        without_desc = Template.from_dict({
            "name": "without-desc",
            "template": "Hello!",
        })

        with_desc_report = scorer.score(with_desc.config)
        without_desc_report = scorer.score(without_desc.config)

        with_desc_completeness = with_desc_report.dimensions[
            QualityDimension.COMPLETENESS
        ].score
        without_desc_completeness = without_desc_report.dimensions[
            QualityDimension.COMPLETENESS
        ].score

        assert with_desc_completeness > without_desc_completeness

    def test_efficiency_score_token_count(self) -> None:
        """Test efficiency score considers token count."""
        scorer = QualityScorer()

        short = Template.from_dict({
            "name": "short",
            "template": "Hello, {{name}}!",
            "variables": [{"name": "name", "type": "string"}],
        })

        long_content = "This is a very long template. " * 500
        long_template = Template.from_dict({
            "name": "long",
            "template": long_content + "{{name}}",
            "variables": [{"name": "name", "type": "string"}],
        })

        short_report = scorer.score(short.config)
        long_report = scorer.score(long_template.config)

        short_efficiency = short_report.dimensions[QualityDimension.EFFICIENCY].score
        long_efficiency = long_report.dimensions[QualityDimension.EFFICIENCY].score

        assert short_efficiency > long_efficiency

    def test_structure_score_split_prompts(self) -> None:
        """Test structure score prefers split prompts."""
        scorer = QualityScorer()

        split = Template.from_dict({
            "name": "split",
            "system_prompt": "You are an assistant.",
            "user_prompt": "Help with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        single = Template.from_dict({
            "name": "single",
            "template": "You are an assistant. Help with {{task}}.",
            "variables": [{"name": "task", "type": "string"}],
        })

        split_report = scorer.score(split.config)
        single_report = scorer.score(single.config)

        split_structure = split_report.dimensions[QualityDimension.STRUCTURE].score
        single_structure = single_report.dimensions[QualityDimension.STRUCTURE].score

        assert split_structure >= single_structure

    def test_suggestions_generated(self) -> None:
        """Test that suggestions are generated for low scores."""
        scorer = QualityScorer()

        template = Template.from_dict({
            "name": "needs-work",
            "template": "{{x}}",
            "variables": [{"name": "x", "type": "string"}],
        })

        report = scorer.score(template.config)

        # Should have suggestions
        assert len(report.top_suggestions) > 0

        # Suggestions should be actionable
        for suggestion in report.top_suggestions:
            assert len(suggestion) > 10  # Not empty

    def test_summary_matches_grade(self) -> None:
        """Test that summary text matches the grade."""
        scorer = QualityScorer()

        template = Template.from_dict({
            "name": "test",
            "template": "Hello!",
        })

        report = scorer.score(template.config)

        if report.grade == "A":
            assert "excellent" in report.summary.lower()
        elif report.grade == "B":
            assert "good" in report.summary.lower()
        elif report.grade == "C":
            assert "acceptable" in report.summary.lower()
        elif report.grade == "D":
            assert "below" in report.summary.lower()
        else:
            assert "poor" in report.summary.lower()
