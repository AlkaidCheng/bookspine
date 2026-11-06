//! pulldown-cmark, as the Python module `guidebook._markdown`.

use pyo3::prelude::*;

#[pymodule]
mod _markdown {
    use pulldown_cmark::{Options, Parser, html};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    #[pymodule_export]
    const ENABLE_DEFINITION_LIST: u32 = Options::ENABLE_DEFINITION_LIST.bits();
    #[pymodule_export]
    const ENABLE_HEADING_ATTRIBUTES: u32 = Options::ENABLE_HEADING_ATTRIBUTES.bits();
    #[pymodule_export]
    const ENABLE_MATH: u32 = Options::ENABLE_MATH.bits();
    #[pymodule_export]
    const ENABLE_SMART_PUNCTUATION: u32 = Options::ENABLE_SMART_PUNCTUATION.bits();
    #[pymodule_export]
    const ENABLE_TABLES: u32 = Options::ENABLE_TABLES.bits();

    /// Return `markdown` as HTML, reading the extensions set in `options`.
    #[pyfunction]
    fn to_html(markdown: &str, options: u32) -> PyResult<String> {
        let options = Options::from_bits(options)
            .ok_or_else(|| PyValueError::new_err(format!("unknown option bits: {options:#x}")))?;
        let mut output = String::with_capacity(markdown.len());
        html::push_html(&mut output, Parser::new_ext(markdown, options));
        Ok(output)
    }
}
