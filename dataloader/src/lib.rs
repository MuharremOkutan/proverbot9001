
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::fs::File;
use std::io::{BufRead, BufReader, Result, Lines};

// enum PyTensor {
//     Long2DTensor(Vec<Vec<i64>>),
//     Float2DTensor(Vec<Vec<f64>>),
// }

#[derive(Debug)]
struct ScrapedTactic {
    relevant_lemmas: Vec<String>,
    prev_tactics: Vec<String>,
    hypotheses: Vec<String>,
    goal: String,
    tactic: String,
}

type PyTensor = Vec<Vec<i64>>;

#[pyfunction]
fn load_data(filename: String) -> PyResult<Option<Vec<PyTensor>>> {
    println!("Reading dataset.");
    match File::open(filename) {
        Result::Ok(file) => {
            for tactic in TacticIterator::new(file) {
                println!("{:?}", tactic);
                break;
            }
            Ok(None)
        }
        Result::Err(err) => {
            println!("Failed to open file: {}", err);
            Ok(None)
        }
    }
}

struct TacticIterator {
    line_iter: Lines<BufReader<File>>,
}
impl TacticIterator {
    fn new(file: File) -> TacticIterator {
        TacticIterator{line_iter: BufReader::new(file).lines()}
    }
    fn lines_until_starline(&mut self) -> Vec<String> {
        let mut result = Vec::new();
        let mut next_line = self.line_iter.next();
        loop {
            match &next_line {
                Some(Ok(ref line)) => {
                    if line == "*****" {
                        break;
                    } else if line != "" {
                        result.push(line.clone());
                    }
                    next_line = self.line_iter.next();
                }
                _ => {break;}
            }
        }
        result
    }
}
impl Iterator for TacticIterator {
    type Item = ScrapedTactic;
    fn next(&mut self) -> Option<ScrapedTactic> {
        let mut lines = vec![];
        let mut next_line = self.line_iter.next()?.unwrap();
        while next_line != "-----" && next_line != "*****"{
            println!("looking at line {}", next_line);
            lines.push(next_line);
            next_line = self.line_iter.next()?.unwrap();
        }
        println!("terminated at line {}", next_line);
        if lines.len() == 0 {
            return None
        } else if lines.len() == 1 {
            println!("Skipping {}", lines[0]);
            return self.next()
        }
        println!("First line is {}", next_line);
        let prev_tactics = self.lines_until_starline();
        let hyps = self.lines_until_starline();
        // let lemmas = self.lines_until_starline();
        let goal = self.line_iter.next()?.unwrap();
        self.line_iter.next();
        let tactic = self.line_iter.next()?.unwrap();
        Some(ScrapedTactic{relevant_lemmas: Vec::new(),
                           prev_tactics: prev_tactics,
                           hypotheses: hyps,
                           goal: goal,
                           tactic: tactic})
    }
}

#[pymodule]
fn dataloader(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(load_data))?;
    Ok(())
}
