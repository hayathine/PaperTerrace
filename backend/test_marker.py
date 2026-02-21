from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


def test():
    print("Loading models...")
    models = create_model_dict()
    converter = PdfConverter(artifact_dict=models)

    print("Converting PDF...")
    # marker 0.3+ api
    rendered = converter("sample.pdf")
    text, _, _ = text_from_rendered(rendered)

    with open("sample_out.md", "w", encoding="utf-8") as f:
        f.write(text)
    print("Saved to sample_out.md")


if __name__ == "__main__":
    test()
