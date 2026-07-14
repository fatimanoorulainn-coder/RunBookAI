"""
RunBookAI LLM Tool Schemas

Tools available to the agent:
1. query_service_metadata
2. search_logs
3. submit_finding
"""


TOOLS = [

    {
        "type": "function",
        "function": {

            "name": "query_service_metadata",

            "description":
                "Retrieve service health metadata from PostgreSQL including deployments and pods.",

            "parameters": {

                "type": "object",

                "properties": {

                    "service_name": {

                        "type": "string",

                        "description":
                            "The Kubernetes service name"

                    }

                },

                "required": [
                    "service_name"
                ]
            }
        }
    },


    {
        "type": "function",
        "function": {

            "name": "search_logs",

            "description":
                "Search service logs for errors, failures, and patterns.",

            "parameters": {

                "type": "object",

                "properties": {

                    "service_name": {

                        "type": "string"

                    },


                    "pattern": {

                        "type": "string"

                    }

                },

                "required": [
                    "service_name",
                    "pattern"
                ]
            }
        }
    },


    {
        "type": "function",
        "function": {

            "name": "submit_finding",

            "description":
                "Submit the final investigation result after evidence collection.",

            "parameters": {

                "type": "object",

                "properties": {


                    "root_cause": {

                        "type": "string"

                    },


                    "status": {

                        "type": "string",

                        "enum": [

                            "resolved",

                            "insufficient_evidence"

                        ]

                    },


                    "confidence_score": {

                        "type": "number"

                    },


                    "missing_evidence": {

                        "type": "array",

                        "items": {

                            "type": "string"

                        }

                    }

                },


                "required": [

                    "root_cause",

                    "status",

                    "confidence_score",

                    "missing_evidence"

                ]

            }
        }
    }

]