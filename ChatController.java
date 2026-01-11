package com.hbj.code2doc.service.RAGService;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/chat")
public class RAGService {

    private static final Logger logger = LoggerFactory.getLogger(RAGService.class);

    @Autowired
    private RAGService ragService;

    @PostMapping("/completions/stream")
    public ResponseEntity<?> chatCompletionsStream(@RequestBody ChatRequest request) {
        logger.info("Processing chat completions stream request");
        return ragService.processChatRequest(request);
    }
}