from app.services import workflows


def test_img2img_workflow_uses_controlnet_canny_structure_settings():
    workflow = workflows.get_img2img_workflow("modern kitchen", "reference.png")

    assert workflow["10"]["inputs"]["image"] == "reference.png"
    assert workflow["11"]["class_type"] == "CannyEdgePreprocessor"
    assert workflow["11"]["inputs"]["resolution"] == 1024
    assert workflow["13"]["inputs"]["strength"] == 0.75
    assert workflow["15"]["inputs"]["denoise"] == 0.75


def test_txt2img_workflow_has_no_reference_image_nodes():
    workflow = workflows.get_txt2img_workflow("modern kitchen")

    assert "10" in workflow
    assert all(node.get("class_type") != "LoadImage" for node in workflow.values())


def test_black_cabinet_prompt_discourages_wood_and_brown_cabinets():
    workflow = workflows.get_img2img_workflow(
        "minimalist kitchen, high gloss black cabinet finish, reflective deep black surfaces",
        "reference.png",
    )

    negative_prompt = workflow["7"]["inputs"]["text"].lower()
    assert "brown cabinets" in negative_prompt
    assert "natural wood grain cabinet fronts" in negative_prompt
    assert "raised panel shaker doors" in negative_prompt
