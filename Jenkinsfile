pipeline {
  agent any
  stages {
    stage('Checkout SCM') {
      steps {
        script {
          checkout scm
        }
        
      }
    }
    stage("lint") {
      steps {
        /*
         * Any Pipeline steps and wrappers can be used within the "steps" section
         * of a Pipeline and they can be nested.
         * Refer to the Pipeline Syntax Snippet Generator for the correct syntax of any step or wrapper
         */
          sh 'pwd'
          sh 'ls -alh'
          sh 'yamllint -d yamllint.yml ./'
      }
    }
  }
}
