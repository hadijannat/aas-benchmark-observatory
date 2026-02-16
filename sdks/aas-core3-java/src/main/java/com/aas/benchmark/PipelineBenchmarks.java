package com.aas.benchmark;

import aas_core.aas3_0.jsonization.Jsonization;
import aas_core.aas3_0.reporting.Reporting;
import aas_core.aas3_0.types.model.IClass;
import aas_core.aas3_0.types.model.IEnvironment;
import aas_core.aas3_0.types.model.IProperty;
import aas_core.aas3_0.verification.Verification;
import aas_core.aas3_0.xmlization.Xmlization;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.RunnerException;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

import javax.xml.stream.XMLEventReader;
import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLOutputFactory;
import javax.xml.stream.XMLStreamWriter;
import java.io.File;
import java.io.IOException;
import java.io.StringReader;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(1)
@State(Scope.Benchmark)
public class PipelineBenchmarks {

    @Param({})
    public String dataset;

    @Param({})
    public String xmlDataset;

    private String rawJson;
    private JsonNode jsonNode;
    private IEnvironment env;
    private final ObjectMapper mapper = new ObjectMapper();

    // XML fields
    private String rawXml;
    private IEnvironment xmlEnv;
    private final XMLInputFactory xmlInputFactory = XMLInputFactory.newInstance();
    private final XMLOutputFactory xmlOutputFactory = XMLOutputFactory.newFactory();

    @Setup(Level.Trial)
    public void setup() throws Exception {
        String datasetsDir = System.getenv("DATASETS_DIR");
        if (datasetsDir == null || datasetsDir.isEmpty()) {
            throw new IllegalStateException("DATASETS_DIR environment variable not set");
        }

        // Load JSON dataset (may be empty placeholder when only XML datasets exist)
        if (dataset != null && !dataset.equals("__none__")) {
            Path jsonPath = Path.of(datasetsDir, dataset + ".json");
            rawJson = Files.readString(jsonPath);
            jsonNode = mapper.readTree(rawJson);
            env = Jsonization.Deserialize.deserializeEnvironment(jsonNode);
        }

        // Load XML dataset (may be empty placeholder when only JSON datasets exist)
        if (xmlDataset != null && !xmlDataset.equals("__none__")) {
            Path xmlPath = Path.of(datasetsDir, xmlDataset + ".xml");
            rawXml = Files.readString(xmlPath);
            XMLEventReader reader = xmlInputFactory.createXMLEventReader(new StringReader(rawXml));
            xmlEnv = Xmlization.Deserialize.deserializeEnvironment(reader);
        }
    }

    // -----------------------------------------------------------------------
    // JSON benchmarks
    // -----------------------------------------------------------------------

    @Benchmark
    public IEnvironment deserialize() throws Exception {
        if (rawJson == null) return null;
        JsonNode node = mapper.readTree(rawJson);
        return Jsonization.Deserialize.deserializeEnvironment(node);
    }

    @Benchmark
    public int validate() {
        if (env == null) return 0;
        int errorCount = 0;
        for (Reporting.Error error : Verification.verify(env)) {
            errorCount++;
        }
        return errorCount;
    }

    @Benchmark
    public int traverse() {
        if (env == null) return 0;
        int count = 0;
        for (IClass node : env.descend()) {
            count++;
        }
        return count;
    }

    @Benchmark
    public int update() {
        if (env == null) return 0;
        int count = 0;
        List<IProperty> touched = new ArrayList<>();
        List<String> originals = new ArrayList<>();
        for (IClass node : env.descend()) {
            if (node instanceof IProperty prop) {
                if (prop.getValue().isPresent()) {
                    String original = prop.getValue().get();
                    prop.setValue(original + "_updated");
                    touched.add(prop);
                    originals.add(original);
                    count++;
                }
            }
        }
        // Restore baseline state so each JMH sample starts from identical data.
        for (int i = 0; i < touched.size(); i++) {
            touched.get(i).setValue(originals.get(i));
        }
        return count;
    }

    @Benchmark
    public JsonNode serialize() {
        if (env == null) return null;
        return Jsonization.Serialize.toJsonObject(env);
    }

    // -----------------------------------------------------------------------
    // XML benchmarks (SRQ-1)
    // -----------------------------------------------------------------------

    @Benchmark
    public IEnvironment deserializeXml() throws Exception {
        if (rawXml == null) return null;
        XMLEventReader reader = xmlInputFactory.createXMLEventReader(new StringReader(rawXml));
        return Xmlization.Deserialize.deserializeEnvironment(reader);
    }

    @Benchmark
    public String serializeXml() throws Exception {
        if (xmlEnv == null) return null;
        StringWriter stringOut = new StringWriter();
        XMLStreamWriter writer = xmlOutputFactory.createXMLStreamWriter(stringOut);
        Xmlization.Serialize.to(xmlEnv, writer);
        writer.flush();
        writer.close();
        return stringOut.toString();
    }

    // -----------------------------------------------------------------------
    // main(): dynamic dataset discovery + GC profiler (SRQ-2)
    // -----------------------------------------------------------------------

    public static void main(String[] args) throws RunnerException, IOException {
        // Discover datasets dynamically
        String datasetsDir = System.getenv("DATASETS_DIR");
        if (datasetsDir == null || datasetsDir.isEmpty()) {
            throw new IllegalStateException("DATASETS_DIR environment variable not set");
        }

        File dir = new File(datasetsDir);

        // Discover JSON datasets
        File[] jsonFiles = dir.listFiles((d, name) -> name.endsWith(".json"));
        List<String> jsonNames = new ArrayList<>();
        if (jsonFiles != null) {
            for (File f : jsonFiles) {
                String name = f.getName();
                jsonNames.add(name.substring(0, name.length() - 5));
            }
        }

        // Discover XML datasets
        File[] xmlFiles = dir.listFiles((d, name) -> name.endsWith(".xml"));
        List<String> xmlNames = new ArrayList<>();
        if (xmlFiles != null) {
            for (File f : xmlFiles) {
                String name = f.getName();
                xmlNames.add(name.substring(0, name.length() - 4));
            }
        }

        if (jsonNames.isEmpty() && xmlNames.isEmpty()) {
            throw new IllegalStateException("No JSON or XML files found in " + datasetsDir);
        }

        // Use "__none__" placeholder when a tier has no datasets so JMH @Param is satisfied
        String[] jsonParam = jsonNames.isEmpty()
                ? new String[]{"__none__"}
                : jsonNames.toArray(new String[0]);
        String[] xmlParam = xmlNames.isEmpty()
                ? new String[]{"__none__"}
                : xmlNames.toArray(new String[0]);

        String outputPath = System.getenv("JMH_OUTPUT");
        if (outputPath == null) {
            outputPath = "jmh_results.json";
        }

        Options opt = new OptionsBuilder()
                .include(PipelineBenchmarks.class.getSimpleName())
                .param("dataset", jsonParam)
                .param("xmlDataset", xmlParam)
                .addProfiler("gc")
                .resultFormat(ResultFormatType.JSON)
                .result(outputPath)
                .build();

        new Runner(opt).run();
    }
}
